#!/usr/bin/env python3
"""
This is an ISY NodeServer for Somfy URTSii controllers by fahrer16 (Brian Feeney) fahrer@gmail.com
based on the NodeServer template for Polyglot v2 written in Python2/3
by Einstein.42 (James Milne) milne.james@gmail.com
"""

import polyinterface
import sys
from threading import Timer
try:
    import serial
except ImportError as e:
    self.logger.error("PySerial does not appear to be installed.  Run ""pip3 install pyserial"" from a command line. %s", str(e))

LOGGER = polyinterface.LOGGER

class Controller(polyinterface.Controller):
    """
    The Controller Class is the primary node from an ISY perspective. It is a Superclass
    of polyinterface.Node so all methods from polyinterface.Node are available to this
    class as well.

    Class Variables:
    self.nodes: Dictionary of nodes. Includes the Controller node. Keys are the node addresses
    self.name: String name of the node
    self.address: String Address of Node, must be less than 14 characters (ISY limitation)
    self.polyConfig: Full JSON config dictionary received from Polyglot.
    self.added: Boolean Confirmed added to ISY as primary node

    Class Methods (not including the Node methods):
    start(): Once the NodeServer config is received from Polyglot this method is automatically called.
    addNode(polyinterface.Node): Adds Node to self.nodes and polyglot/ISY. This is called for you
                                 on the controller itself.
    delNode(address): Deletes a Node from the self.nodes/polyglot and ISY. Address is the Node's Address
    longPoll(): Runs every longPoll seconds (set initially in the server.json or default 10 seconds)
    shortPoll(): Runs every shortPoll seconds (set initially in the server.json or default 30 seconds)
    query(): Queries and reports ALL drivers for ALL nodes to the ISY.
    runForever(): Easy way to run forever without maxing your CPU or doing some silly 'time.sleep' nonsense
                  this joins the underlying queue query thread and just waits for it to terminate
                  which never happens.
    """
    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot)
        self.serialPort = ""
        self._ser = None
    
    def _createDefaultConfig(self):
        """
        This method will create the default configuration parameters if they do not exist
        the user can then change them from the defaults, if required
        """
        try:
            if self.polyConfig['customParams']['port'] is None:
                self.polyConfig['customParams']['port'] = "/dev/ttyUSB0" #Assuming most folks would use a USB-RS232 adapter, default to USB port.
        except Exception as ex:
            LOGGER.error('Error writing default configuration: %s', str(ex))
        self.serialPort = "/dev/ttyUSB0"
        return True

    def start(self):
        LOGGER.info('Started Somfy URTSii NodeServer')
        # Get configuration
        try:
            self.serialPort = self.polyConfig['customParams']['port']
            if self.serialPort is None:
                LOGGER.info('"port" key not found in Node configuration')
                self._createDefaultConfig()
        except Exception as ex:
            LOGGER.error('Error reading configuration.  Attempting to create default configuration: %s', str(ex))
            self._createDefaultConfig()
        self.discover() 
        return True

    def shortPoll(self):
        pass

    def longPoll(self):
        pass

    def query(self):
        for node in self.nodes:
            self.nodes[node].reportDrivers()

    def discover(self, *args, **kwargs):
        """Add Nodes for Somfy Blinds
           Build address for node.  Format is SerialPort#_Address#_Channel#.  For example, 01_01_01 is serial port #1 (none other currently possible), URTS controller 1 (none other currently possible), URTS channel # (1-16)
        """
        _address = "01_01_" #TODO: Add ability to specify multiple serial ports with multiple URTSii controllers on each port.  This will default to serial port 1, address 1 allowing a single URTSii interface
        for ch in range(1,16): #TODO: Add ability to specify channels rather than creating all 16
                _chAddress = _address + str(ch).rjust(2,"0")
                _chName = "Shade " + _chAddress
                if _chAddress not in self.nodes:
                    self.addNode(SomfyShade(self, self.address, _chAddress, _chName)) #TODO: Add ability to create Blinds, which use two channels (one for up/down, one for tilt)
                    
    def connect(self):
        #Check that we have the info we need to continue:
        if self.serialPort is None:
            self.set_driver('GV1',False)
            raise ValueError('Somfy Serial Port not specified')
        
        if self._ser is not None:
            if self._ser.is_open:
                #Already connected, no need to connect again
                return True
          
        #Connect to Serial Port:
        try:
            self._ser = serial.Serial(port) #Default baud, data bits, stop bit, and parity matches up with the URTSii, no need to specify 
            self.set_driver('GV1', self._ser.is_open)
            return True
        except Exception as ex:
            #If we got through to here, there were too many failure attempting to connect
            self.set_driver('GV1',False)
            LOGGER.error('Serial Port Connection Error on connect.  Check "port" key setting in Polyglot config (%s). %s', str(self.serialPort), str(ex))
        return False

    def _sendURTSCmd(self, command = ""):
        if str(command) == "": return False
        _tries = 0
        while _tries <= 2:
            try:
                    if not self.ser.is_open:
                        self.connect()
                    self.ser.write(command)
                    self.set_driver('GV1',self.ser.is_open)
                    return True
            except Exception as ex:
                    _tries = _tries + 1
                    _errorMsg = str(ex)
                    LOGGER.error('Serial Port Connection Error on SomfyNodeServer sendURTSCmd.  Check Serial Port Connection', str(ex))
        #If we got through the while loop above, there were multiple failures.  Set the "Connected" status to "False"
        self.set_driver('GV1',False)
        return False

    def command(self, node_address, command):
        try:
            if str(command) == "": return False
            _serialPort = int(node_address[:1].lstrip("0")) #TODO: Currently only using one serial port for this project, this will be needed if it is expanded to allow multiple serial ports
            _prefix = node_address[3:].replace("_","") #Get the portion of the node's address that corresponds to the URTSii address and channel then remove the underscore to format it for the URTSii command
            _command = str(command)
            return _sendURTSCmd(_prefix + _command + "\r")
        except Exception as ex:
            LOGGER.error('Error parsing Somfy command (%s) for address (%s). %s', str(node_address), str(command), str(ex))
            return False

    id = 'controller'
    commands = {'DISCOVER': discover}
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 2}, #Node Server Connected
                {'driver': 'GV1', 'value': 0, 'uom': 2}] #Serial Port Connected


class SomfyShade(polyinterface.Node):
    """
    Class Variables:
    self.primary: String address of the Controller node.
    self.parent: Easy access to the Controller Class from the node itself.
    self.address: String address of this Node 14 character limit. (ISY limitation)
    self.added: Boolean Confirmed added to ISY

    Class Methods:
    start(): This method is called once polyglot confirms the node is added to ISY.
    setDriver('ST', 1, report = True, force = False):
        This sets the driver 'ST' to 1. If report is False we do not report it to
        Polyglot/ISY. If force is True, we send a report even if the value hasn't changed.
    reportDrivers(): Forces a full update of all drivers to Polyglot/ISY.
    query(): Called when ISY sends a query request to Polyglot for this specific node
    """
    def __init__(self, parent, primary, address, name):
        super(SomfyShade, self).__init__(parent, primary, address, name)

    def start(self, command):
        self.position = -1 #TODO: Is there a way to read the current values from this node in the ISY (if it exists already) and populate local variables here?  It would help not to lose track of shade state if restarting the node server
        self.lastCmdTime = 0
        self.lastCmd = ""
        
        """
        Read this shade's travel time from the polyglot config.
        Since the URTSii does not track/report shade position, this will allow for infering the shade's position based on
        the time it takes for the shade to transition from fully closed to fully open
        """
        try:
            self.travelTime = self.polyConfig['customParams'][str(address)]
            if self.travelTime is None:
                self.logger.info('No travel time found in polyglot config for %s.  Defaulting to 2 seconds', self.address)
                self.travelTime = 2
        except Exception as ex:
            LOGGER.info('Error reading travel time from polyglot config for %s.  Defaulting to 2 seconds', self.address)
            self.travelTime = 2

    def query(self, command):
        if self.position >= 0: self.set_driver('ST',self.position)
        self.set_driver('GV1',self.travelTime)
        self.reportDrivers()
        
    def down(self, command):
        LOGGER.info('Received DOF command on %s',self.address)
        return setShadePosition(0)
    
    def up5(self, command):
        if self.position == -1:
            LOGGER.error('BRT command received on %s but current shade position not known', self.address)
            return False
        else:
            LOGGER.info('Received BRT command on %s', self.address)
            return setShadePosition(self.position + 5)
        
    def down5(self, command):
        if self.position == -1:
            LOGGER.error('DIM command received on %s but current shade position not known', self.address)
            return False
        else:
            self.logger.info('Received DIM command on %s', self.address)
            return setShadePosition(self.position - 5)
        
    def up(self, command):
        LOGGER.info('Received DON command on %s', self.address)
        _position = command.get('value')
        _success = false
        if _position is None:
            return setShadePosition(100)
        else:
            return setShadePosition(_position)

    def stop(self, command):
        LOGGER.info('Received STOP command on %s: %s', self.address, str(command))
        return self._stop()
    
    def _stop(self):
        _success = self.parent.command(self.address, "S")
        _updatePosition()
        return _success
    
    def _command(self, timeSP, command, nextCmd=""):
        _command = str(command)[0]
        self.parent.command(self.address, _command)
        self.lastCmdTime = time.time() #UTC epoch time in seconds
        self.lastCmd = _command
        #Start Update Position Timer
        try:
            self.timer.cancel()
            if str(nextcmd) == "S":
                self.timer = Timer(timeSP, self._stop)           
            elif nextcmd.isdigit():
                self.timer = Timer(timeSP, self.setShadePosition,args=[nextCmd])
            else:
                self.timer = Timer(timeSP, self._updatePosition)
            self.timer.start()
            LOGGER.debug("Starting shade position timer on %s for %i seconds", self.address, timeSP)
            return True
        except Exception as ex:
            LOGGER.error('Error starting shade position timer on %s.', self.address)
            return False

    
    def setShadePosition(self, positionSP):	
        _updatePosition() #Will stop update position timer, if running
        _success = false
        if positionSP <= 0:
            _success = _command(self.travelTime, "D")
        elif positionSP >= 100:
            _success = _command(self.travelTime, "U")
        elif self.position == -1: #Current Position is not known.  Put the shade down, wait for the travel time, then put it up to the specified percentage:
            _success = _command(self.travelTime, "D",positionSP) #open the shade to the requsted position after the travel time when the shade should be down.
        else:
            _travelTimeReqd = abs(self.travelTime * (positionSP - self.position) / 100.)
            if _position > self.position:
                _success = _command(_travelTimeReqd, "U", "S")
            else :
                _success = _command(_travelTimeReqd, "D", "S")
        return _success
      
    def _updatePosition(self):
        #Attempt to stop the position timer if it's running:
        try:
            self.timer.cancel()
        except Exception as ex:
            LOGGER.debug('Error stopping shade position timer on %s.  Time may not have been created yet: %s', self.address, str(ex))

        _now = time.time()
        _timeDifference = max(_now - self.lastCmdTime,0)
        if _timeDifference >= float(self.travelTime):
            if self.lastCmd == "U":
                self.position = 100.
            elif self.lastCmd == "D":
                self.position = 0.
        elif _timeDifference > 0. and self.position > 0:
            _travel = _timeDifference / float(self.travelTime) * 100.
            if self.lastCmd == "U":
                self.position =  max(min(self.position + _travel,100.),0.)
            elif self.lastCmd == "D":
                self.position = max(min(self.position - _travel,100.),0.)
        if self.position >= 0: self.set_driver('ST',self.position)
        self.lastCmdTime = time.time()
        self.lastCmd = ""
        return True
    
    def setTravelTime(self, command):
        _time = command.get('value')
        if _time is None:
            LOGGER.info('Received command to change %s travel time but no value received: %s', self.address, str(command))
            return False
        elif not _time.isdigit():
            LOGGER.info('Received command to change %s travel time invalid value received: %s', self.address, str(command))
            return False
        elif _time < 0 or _time > 60:
            LOGGER.info('Received command to change %s travel time but value is out of range', self.address, _time)
        else:
            LOGGER.info('Received command to change %s travel time to %i', self.address, _time)
            self.travelTime = _time
            self.set_driver('GV1', self.travelTime)
            return True
            
    
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 51}, {'driver': 'GV1', 'value': 2, 'uom':58}] #ST=position (0-100%), GV1=Travel Time (seconds)
    id = 'somfyshade'
    commands = {
                    'DON': up, 'DOF': down, 'BRT': up5, 'DIM': down5, 'QUERY': query, 'STOP': stop, 'SET_TRAVEL_TIME': setTravelTime
                }


if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('Somfy')
        """
        Instantiates the Interface to Polyglot.
        """
        polyglot.start()
        """
        Starts MQTT and connects to Polyglot.
        """
        control = Controller(polyglot)
        """
        Creates the Controller Node and passes in the Interface
        """
        control.runForever()
        """
        Sits around and does nothing forever, keeping your program running.
        """
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
        """
        Catch SIGTERM or Control-C and exit cleanly.
        """
