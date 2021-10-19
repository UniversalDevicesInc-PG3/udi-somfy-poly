
# Configuration

	* Set the _port_ custom configuration parameter to the serial port that the URTSii is connected to.  Any valid serial port may be specified.

If the URTSii will be connected to a remote machine, a program will need to be running to accept the commands.  This has been tested using a TCP node connected to a Serial Node in Node-Red(https://nodered.org/).

	* Set the _port_ custom configuration parameter to the URL.

see [pySerial](http://pythonhosted.org/pyserial/url_handlers.html#overview) documentation.

Example: 'socket://192.168.1.100:7777' would send TCP packets containing the serial instructions to a host with IP address 192.168.1.100 on port 7777.

The Somfy URTSii interface only allows for sending commands, it does not receive feedback to know the shade position.  In order to provide a shade position in the ISY, the time it takes for the shade to travel from fully closed to fully open is used.  If the shade travels for half of this time, it's assumed to be at 50%.
Each shade's travel time can be specified in the polyglot configuration.  
	* For each shade, create a key corresponding to its address seen in the admin console.  For example, if the shade's address is shown as 'n001_01_01_01', create a key '01_01_01'.  It's value is the number seconds corresponding to the shade's travel time.

If no travel time is specified, the node will use a default value of 8 seconds.  The time can also be specified in the ISY using a command, but note that this will not persist across node server reboots.
	
