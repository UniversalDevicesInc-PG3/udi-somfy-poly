#!/usr/bin/env python3
"""
This is an ISY NodeServer for Somfy URTSii controllers by fahrer16 (Brian Feeney) fahrer@gmail.com
based on the NodeServer template for Polyglot v2 written in Python2/3
by Einstein.42 (James Milne) milne.james@gmail.com
"""

import udi_interface
import sys
from threading import Timer
import serial
import json
from os.path import join, expanduser
import requests
import time

LOGGER = udi_interface.LOGGER
SERVERDATA = json.load(open('server.json'))
VERSION = SERVERDATA['credits'][0]['version']

class Controller(udi_interface.Node):
    def __init__(self, polyglot, primary, address, name):
        super(Controller, self).__init__(polyglot, primary, address, name)
        self.poly = polyglot
        self.serialPort = ""
        self.name = 'Somfy Controller'
        self._ser = None
        self.travelTime = {}

        polyglot.subscribe(polyglot.START, self.start, address)
        polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)
        polyglot.subscribe(polyglot.POLL, self.poll)

        polyglot.ready()
        polyglot.addNode(self, conn_status="ST")

    def parameterHandler(self, params):
        self.poly.Notices.clear()
        try:
            if 'port' in params:
                self.serialPort = params['port']
                LOGGER.debug('got serial port configuration from polyglot, port = %s', str(self.serialPort))

            if self.serialPort == "":
                self.poly.Notices['port'] = 'Please enter a valid port device'

            for key,val in params.items():
                if key == 'port':
                    continue
                self.travelTime[key] = value

        except Exception as ex:
            LOGGER.error('Error reading configuration.')
    
    def start(self):
        LOGGER.info('Starting Somfy URTSii NodeServer version %s', str(VERSION))

        while self.serialPort == "":
            time.sleep(1)

        if self.connectSerial(): LOGGER.info('Connected to serial port %s', str(self.serialPort))
        self.discover() 
        return True

    def poll(self, polltype):
        if 'longPoll' in polltype:
            LOGGER.debug('Executing longPoll')
            if self.serialPort != "":
                self.connectSerial()

    def query(self):
        for node in self.poly.nodes():
            node.reportDrivers()

    def discover(self, *args, **kwargs):
        """Add Nodes for Somfy Blinds
           Build address for node.  Format is SerialPort#_Address#_Channel#.
           For example, 01_01_01 is serial port #1 (none other currently 
           possible), URTS controller 1 (none other currently possible),
           URTS channel # (1-16)
        """
        LOGGER.info('Discovering somfy nodes')
        _address = "01_01_"
        """
        TODO: Add ability to specify multiple serial ports with multiple
        URTSii controllers on each port.  This will default to serial port
        1, address 1 allowing a single URTSii interface
        """
        #TODO: Add ability to specify channels rather than creating all 16
        for ch in range(1,17):
            _chAddress = _address + str(ch).rjust(2,"0")
            _chName = "Shade_" + _chAddress
            if not self.poly.getNode(_chAddress):
                if _chAddress in self.travelTime:
                    self.poly.addNode(SomfyShade(self.poly, self.address, _chAddress, _chName, self.travelTime[_chAddress]))
                else:
                    self.poly.addNode(SomfyShade(self.poly, self.address, _chAddress, _chName, None))
                #TODO: Add ability to create Blinds, which use two channels (one for up/down, one for tilt)
                    
    def connectSerial(self):     
        if self._ser is not None:
            if self._ser.is_open:
                #Already connected, no need to connect again
                self.setDriver('GV1', 1)
                return True
  
        #Connect to Serial Port:
        _tries = 0
        while _tries <= 1:
            try:
                if '://' in self.serialPort:
                    LOGGER.info('Connecting to serial port via url %s', str(self.serialPort))
                    self._ser = serial.serial_for_url(self.serialPort)
                else:
                    LOGGER.info("Connecting to local serial port %s", str(self.serialPort))
                    self._ser = serial.Serial(port = self.serialPort, baudrate = 9600, bytesize = serial.EIGHTBITS, stopbits = serial.STOPBITS_ONE, parity = serial.PARITY_NONE)
                
                if self._ser.is_open:
                    LOGGER.info("Connected to %s", str(self.serialPort))
                    self.setDriver('GV1', 1)
                    return True
                else:
                    self.setDriver('GV1', 0)
            except Exception as ex:
                _tries += 1
                LOGGER.error('Serial Port Connection Error on connect.  Check "port" key setting in Polyglot config (%s). %s', str(self.serialPort), str(ex))
        #If we got through to here, there were too many failures attempting to connect
        self.disconnectSerial()
        return False

    def disconnectSerial(self):
        self.setDriver('GV1',0)

        if self.serialPort is None:
            return False

        LOGGER.info('Disconnecting serial port %s', str(self.serialPort))

        if self._ser is not None:
                try:
                    self._ser.close()
                    return True
                except Exception as ex:
                    return False
        else:
            LOGGER.error('Command received to close serial port %s but object does not yet exist', str(self.serialPort))
            return False

    def _sendURTSCmd(self, command = ""):
        if str(command) == "": return False
        LOGGER.debug('Writing %s to serial port %s', str(command), str(self.serialPort))
        _tries = 0
        while _tries <= 2:
            try:
                    if self.connectSerial():
                        self._ser.write(command.encode())
                        return True
                    else:
                        _tries += 1
            except Exception as ex:
                    _tries += 1
                    LOGGER.error('Serial Port Connection Error on SomfyNodeServer sendURTSCmd.  Check Serial Port Connection: %s', str(ex))
        #If we got through the while loop above, there were multiple failures.  Set the "Connected" status to "False"
        self.disconnectSerial() #try disconnecting the serial port to force a re-connection
        return False

    def command(self, node_address, command):
        try:
            LOGGER.debug('processing command, address=%s, command=%s', str(node_address), str(command))
            if str(command) == "": return False
            _serialPort = int(node_address[:2].lstrip("0")) #TODO: Currently only using one serial port for this project, this will be needed if it is expanded to allow multiple serial ports
            _prefix = node_address[3:].replace("_","") #Get the portion of the node's address that corresponds to the URTSii address and channel then remove the underscore to format it for the URTSii command
            _command = str(command)
            return self._sendURTSCmd(_prefix + _command + "\r")
        except Exception as ex:
            LOGGER.error('Error parsing Somfy command (%s) for address (%s). %s', str(command), str(node_address), str(ex))
            return False

    def delete(self):
        LOGGER.info('Deleting %s', self.address)
        self.disconnectSerial()

    def _connectSerial(self, command):
        LOGGER.info('Command received to connect serial')
        self._getSerialConfig()
        self.connectSerial()

    def _disconnectSerial(self, command):
        LOGGER.info('Command received to disconnect serial')
        self.disconnectSerial()

    id = 'controller'
    commands = {'DISCOVER': discover, 'CONNECT': _connectSerial, 'DISCONNECT': _disconnectSerial}
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 2}, #Node Server Connected
                {'driver': 'GV1', 'value': 0, 'uom': 2}] #Serial Port Connected


class SomfyShade(udi_interface.Node):
    def __init__(self, polyglot, primary, address, name, travelTime):
        super(SomfyShade, self).__init__(polyglot, primary, address, name)
        self.position = -1 #TODO: Is there a way to read the current values from this node in the ISY (if it exists already) and populate local variables here?  It would help not to lose track of shade state if restarting the node server
        self.lastCmdTime = 0
        self.lastCmd = ""
        self.parent = polyglot.getNode(primary)
        _msg = "Timer created for " + address
        self.timer = Timer(1,LOGGER.debug,[_msg])
        if travelTime is not None:
            self.travelTime = float(travelTime)
        else:
            self.travelTime = 8

        polyglot.subscribe(polyglot.START, self.start, address)

    def start(self):
        """
        Read this shade's travel time from the polyglot config.
        Since the URTSii does not track/report shade position, this will
        allow for infering the shade's position based on the time it takes
        for the shade to transition from fully closed to fully open
        """
        try:
            self.setDriver('GV1',self.travelTime)
            return True
        except Exception as ex:
            LOGGER.error('Error setting travel time from config for %s: %s', self.address, str(ex))
        else:
            LOGGER.info('No travel time found in polyglot config for %s.  Defaulting to 8 seconds', self.address)

    def query(self, command=''):
        if self.position >= 0.: self.setDriver('ST',int(self.position))
        self.setDriver('GV1',self.travelTime)
        self.reportDrivers()
        
    def down(self, command=''):
        LOGGER.info('Received DOF command on %s',self.address)
        return self.setShadePosition(0)
    
    def up5(self, command=''):
        if self.position == -1:
            LOGGER.error('BRT command received on %s but current shade position not known', self.address)
            return False
        else:
            LOGGER.info('Received BRT command on %s', self.address)
            return self.setShadePosition(self.position + 5)
        
    def down5(self, command=''):
        if self.position == -1:
            LOGGER.error('DIM command received on %s but current shade position not known', self.address)
            return False
        else:
            LOGGER.info('Received DIM command on %s', self.address)
            return self.setShadePosition(self.position - 5)
        
    def up(self, command):
        _position = command.get('value')
        if _position is None:
            LOGGER.info('Received DON command on %s', self.address)
            return self.setShadePosition(100)
        else:
            _position = int(_position)
            LOGGER.info('Received command to set %s to %i percent', self.address, _position)
            return self.setShadePosition(_position)

    def stop(self, command):
        """
        #TODO: The stop command has two functions.  If the stop is issued while the shade is moving, it stops.
        #If the shade is already stopped and the stop command is issued, the shade goes to a pre-defined position.  
        #We could have a config setting for what that position is to keep the position in the ISY updated if a stop is issued while the shade is stopped.
        """
        LOGGER.info('Received STOP command on %s: %s', self.address, str(command))
        return self._stop()
    
    def _stop(self):
        _success = self.parent.command(self.address, "S")
        self._updatePosition() 
        return _success
    
    def _command(self, timeSP, command, nextCmd=""):
        LOGGER.debug('%s processing command, command=%s, timeSP=%s, nextCmd=%s', self.address, str(timeSP), str(command), str(nextCmd))
        _command = str(command)[0] #The command should be a single character, ensuring here that we only use one character
        self.parent.command(self.address, _command) #Send command to serial port through controller node
        self.lastCmdTime = time.time() #UTC epoch time in seconds
        self.lastCmd = _command
        #Start Update Position Timer
        try:
            if self.timer is not None:
                self.timer.cancel()
            if str(nextCmd) == "S":
                self.timer = Timer(timeSP, self._stop)           
            elif self._isNumeric(nextCmd):
                self.timer = Timer(timeSP, self.setShadePosition,args=[nextCmd])
            else:
                self.timer = Timer(timeSP, self._updatePosition)
            self.timer.start()
            LOGGER.debug("Starting shade position timer on %s for %s seconds", self.address, str(timeSP))
            return True
        except Exception as ex:
            LOGGER.error('Error starting shade position timer on %s. %s', self.address, str(ex))
            return False

    def _isNumeric(self, value):
        try:
            _temp = float(value)
            return True
        except Exception as ex:
            return False
    
    def setShadePosition(self, positionSP):	
        self._updatePosition() #Will stop update position timer, if running
        _success = False
        if positionSP <= 0:
            _success = self._command(self._travelTimeReqd(positionSP), "D")
        elif positionSP >= 100:
            _success = self._command(self._travelTimeReqd(positionSP), "U")
        elif self.position == -1: #Current Position is not known.  Put the shade down, wait for the travel time, then put it up to the specified percentage:
            _success = self._command(self._travelTimeReqd(positionSP), "D",positionSP) #open the shade to the requsted position after the travel time when the shade should be down.
        else:
            if positionSP > self.position:
                _success = self._command(self._travelTimeReqd(positionSP), "U", "S")
            else :
                _success = self._command(self._travelTimeReqd(positionSP), "D", "S")
        return _success

    def _travelTimeReqd(self, positionSP):
        try:
            if self.position == -1:
                return self.travelTime
            else:
                """
                Calculate the time it should take to travel from the current position to the commanded position
                Assumes the shade travels at the same speed (fully open to fully closed in *self.travelTime* seconds)
                """
                return abs(self.travelTime * (positionSP - self.position) / 100.)
        except Exception as ex:
            LOGGER.debug('Error calculating travel time required, using default: %s', str(ex))
            return self.travelTime
      
    def _updatePosition(self):
        #Attempt to stop the position timer if it's running:
        try:
            self.timer.cancel()
        except Exception as ex:
            LOGGER.debug('Error stopping shade position timer on %s.  Timer may not have been created yet: %s', self.address, str(ex))

        _now = time.time()
        _timeDifference = max(_now - self.lastCmdTime,0)
        if _timeDifference >= float(self.travelTime):
            if self.lastCmd == "U":
                self.position = 100
            elif self.lastCmd == "D":
                self.position = 0
        elif _timeDifference > 0. and self.position >= 0.:
            _travel = _timeDifference / float(self.travelTime) * 100.
            if self.lastCmd == "U":
                self.position =  int(max(min(self.position + _travel,100.),0.))
            elif self.lastCmd == "D":
                self.position = int(max(min(self.position - _travel,100.),0.))
        
        if self.position >= 0.: self.setDriver('ST',int(self.position))
        self.lastCmdTime = time.time()
        self.lastCmd = ""
        return True
    
    def setTravelTime(self, command):
        try:
            _time = float(command.get('value'))
        except Exception as ex:
            LOGGER.info('Received command to change %s travel time invalid value received: %s', self.address, str(command))
            return False

        if _time < 0 or _time > 60:
            LOGGER.info('Received command to change %s travel time but value is out of range (%s)', self.address, str(_time))
            return False
        else:
            LOGGER.info('Received command to change %s travel time to %s', self.address, str(_time))
            self.travelTime = _time
            self.setDriver('GV1', self.travelTime)
            #TODO: It doesn't appear there's a way to write to the polyglot configuration but it would be nice to write this value to the config here so it doesn't need to be reset
            return True

            
    
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 51}, 
               {'driver': 'GV1', 'value': 2, 'uom':58}] #ST=position (0-100%), GV1=Travel Time (seconds)
    commands = {
                   'DON': up,
                   'DOF': down,
                   'BRT': up5,
                   'DIM': down5,
                   'QUERY': query,
                   'STOP': stop,
                   'SET_TRAVEL_TIME': setTravelTime}
    id = 'somfyshade'


if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start('2.0.0')
        polyglot.updateProfile()
        polyglot.setCustomParamsDoc()
        Controller(polyglot, 'controller', 'controller', 'Somfy')
        polyglot.runForever()

    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
