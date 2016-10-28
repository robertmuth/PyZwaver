## About

PyZwaver is a pure Python3 library for communicating with a serial port based
Z-Wave controller such as Aeotec's Z-Stick.

Its focus is on simplicity and hackability.
A simple webserver app is provided to demonstrate its capabilities.

## Status

PyZwaver is still very much work in progress.
It supports a wide range of Command Classes but many are still missing.

Most notable omissions are:
* Security - this is currently in the works
* Scene support

## Demo

A simple webserver demo can be launched like so:

./webserver.py  --serial_port=/dev/ttyUSB0 --port=44444  --node_auto_refresh_secs=120

you likely need to tweak the *--serial_port* parameter for you setup.


## License

All code is governed by LICENSE.txt (GPL 3) unless otherwise noted.
For alternative licensing please contact the author.

## Dependencies

The core PyZwaver library does not have any non-standard dependencies.

However the webserver demo app depends on:

* tornado
  http://www.tornadoweb.org/

* Static/list.min.js
  http://www.listjs.com/

## Author

robert@muth.org

## References

* http://zwavepublic.com
