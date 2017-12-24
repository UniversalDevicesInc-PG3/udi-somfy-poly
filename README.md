# Somfy Node Server for Polyglot v2
This node server allows the [UDI ISY 994i](http://universal-devices.com/) to control Somfy RTS shades using a [Somfy URTSii serial interface](https://www.somfysystems.com/products/1810872/universal-rts-interface)
The URTSii can be connected to the machine running Polyglot directly or the commands can be issued remotely.  See [Here](http://pythonhosted.org/pyserial/url_handlers.html#overview) and instructions below.

#### Installation
This assumes you have already installed polyglot v2, see [here](https://github.com/Einstein42/udi-polyglotv2)
1. Backup ISY
1. Clone this project into the /.polyglot/nodeservers folder for the user that runs polyglot v2
	*	Assuming you're logged in as the user that runs polyglot, 'cd ~/.polyglot/nodeservers'
	*	'git clone https://github.com/fahrer16/udi-somfy-poly.git'
1. Install pre-requisites
	*	From the node server's directory ('cd udi-somfy-poly'), run 'install.sh'
	Note: you may have to grant execute permission using 'chmod +x ./install.sh' and for installing pySerial, you may need sudo.
1. Add node server to polyglot.
	* 	There are some good instructions for this with screenshots about halfway down [here](https://github.com/Einstein42/udi-polyglotv2/wiki/Creating-a-NodeServer)
1. If the URTSii will be connected to the machine hosting polyglot, the user running polyglot will need permission to access the serial port
	*	There are various ways of accomplishing this, one is to add that user to the dialout group:
		*	'sudo usermod -a -G dialout POLYGLOT_USER_NAME'
	*	The serial port can be specified in the polyglot configuration.
		*	Under nodeserver configuration, add a custom configuration parameter with a key of _port_.  If no key is specified, the default value is '/dev/ttyUSB0' but any serial port can be specified here.
1. If the URTSii will be connected to a remote machine, a program will need to be running to accept the commands.  This has been tested using a TCP node connected to a Serial Node in Node-Red(https://nodered.org/).
	*	The destination can be specified in the polyglot configuration.
		* Under nodeserver configuration add a custom configuration parameter with a key of _port_.  The value will be the URL needed, see [pySerial](http://pythonhosted.org/pyserial/url_handlers.html#overview) documentation.  Example: 'socket://192.168.1.100:7777' would send TCP packets containing the serial instructions to a host with IP address 192.168.1.100 on port 7777.
1.	The Somfy URTSii interface only allows for sending commands, it does not receive feedback to know the shade position.  In order to provide a shade position in the ISY, the time it takes for the shade to travel from fully closed to fully open is used.  If the shade travels for half of this time, it's assumed to be at 50%.
	*	Each shade's travel time can be specified in the polyglot configuration.  
		*	For each shade, create a key corresponding to its address seen in the admin console.  For example, if the shade's address is shown as 'n001_01_01_01', create a key '01_01_01'.  It's value can be a number corresponding to the shade's travel time.
	*	If no travel time is specified, the node will use a default value of 8 seconds.  The time can also be specified in the ISY using a command, but note that this will not persist across node server reboots.
	

Known Issues / ToDo List:
- [ ]	Node currently supports a single URTSii and all 16 channels will be added by default.
- [ ]	Node currently supports only shades, blinds with tilt functions are not yet supported.
- [ ]	Shade positions are not persisted across node server reboots.  If a shade position is specified and the shade does not know the position, it will fully close then open to the requested position.
- [ ]	The stop command has two functions.  If the stop is issued while the shade is moving, it stops.  If the shade is already stopped and the stop command is issued, the shade goes to a pre-defined position.
- [ ]	There doesn't appear to be a way to execute actions when the node server is stopping so the port is not automatically closed.  As a temporary workaround, a command is available on the controller node to close the port before stopping the server.
- [ ]	There doesn't appear to be a way to write programmatically to the polyglot config but it would be nice to write the shade travel times to the config automatically when a command is issued from the ISY to change them.
- [ ]	The automatic upload of the profile to the ISY doesn't seem to provide all of the commands at first.  Following up with a manual upload of profile.zip through the admin console fixes the issue.  Not consistently reproducible at this time.

Version History:
1.0.0: Initial version, written with python 3.5 on a Debian 9 VM on ESXi 6.5 host for Polyglot version 2.0.29 and ISY version 5.0.10E.