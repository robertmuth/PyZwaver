## About

PyZwaver is a pure Python3 library for communicating with a serial port based
Z-Wave controller such as Aeotec's Z-Stick.

Its focus is on simplicity and hackability.
Several simple examples are provided to demonstrate its capabilities.

## Status

PyZwaver is still work in progress.
It supports a wide range of Command Classes but some are still missing.

Most notable omissions are:

* MultiChannel support (in progress)
* Security 

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

### example_tool.py

A command line tool for doing tasks alike parining and unpairing

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

## License

All code is governed by LICENSE.txt (GPL 3) unless otherwise noted.
For alternative licensing please contact the author.

## Dependencies

The core PyZwaver library does not have any non-standard dependencies.

However the example_webserver.py depends on:

* tornado
  http://www.tornadoweb.org/

* Static/list.min.js
  http://www.listjs.com/

## Author

robert@muth.org

## References

* http://zwavepublic.com
