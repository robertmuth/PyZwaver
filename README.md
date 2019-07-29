## About

PyZwaver is a pure Python3 library for communicating with a serial port based
Z-Wave controller such as Aeotec's Z-Stick.

Its focus is on simplicity and hackability.
Several simple examples are provided to demonstrate its capabilities.

## Status

PyZwaver is still work in progress.
It supports a wide range of Command Classes but some are still missing.

Most notable omissions are:

* Security (stalled because crypto protocol documentation lacks concrete examples)

## Examples

All examples accept a *--serial_port* parameter which has to be
adjusted to match the local setup.

### example_simple.py

A command line tool which can be launched like so.
It will print some basic information about the controller and
all the nodes paired with it. It will not return until it had a 
chance to communicate with all nodes.

```
./example_simple.py  --serial_port=/dev/ttyUSB0 
```

(Make sure you habe permission to access the serial port.
On Linux this may involve becoming a member of certain groups
like 'dialout'.)

### example_tool.py

A command line tool for doing tasks alike parining and unpairing

### example_mqtt.py

A mqtt client which forwards commands - both ways.

### example_webserver.py

A simple webserver which can be launched like so:

```
./webserver.py  --serial_port=/dev/ttyUSB0 --port=44444
```

Then start exploring using the URL:
http://localhost:44444

## Testing

Rudimentary test can be run with

````
make tests
````

## Architectural Overview

see [Architectural Overview](ARCHITECTURE.md)

## Supporting New Command Classes

The message format of all support Command Classes is described 
in machine readable form in [constants_generator.py](constants_generator.py)
This can be used to generate python code (see Makefile target)
for [zwave.py](pyzwaver/zwave.py). 

The generated code in combination with 
[command.py](pyzwaver/command.py) represents
a assembler/disassembler for zwave commands
(see entry points: AssembleCommand/ParseCommand).

Handling of parsed commands occurs in [node.py](pyzwaver/node.py)


## License

All code is governed by LICENSE.txt (GPL 3) unless otherwise noted.
For alternative licensing please contact the author.

## Dependencies

The core PyZwaver library only depends on python3-serial.

Some examples require additional libraries:

example_webserver.py depends on:

* tornado
  http://www.tornadoweb.org/

* Static/list.min.js
  http://www.listjs.com/

example_mqtt.py depends on:

* paho.mqtt
  https://pypi.org/project/paho-mqtt/
  
## Author

robert@muth.org

## References

* http://zwavepublic.com
