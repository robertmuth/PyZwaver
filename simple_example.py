#!/usr/bin/python3
# Copyright 2016 Robert Muth <robert@muth.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; version 3
# of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

"""
Simple Webserver built on top of PyZwaver

Usage:
Run
    ./webserver --serial_port=<usb-zwave-device>
Common values for usb-zwave-device are:
    /dev/ttyUSBx
    /dev/ttyACMx
Then navigate to
    http:://localhost:55555
in your browser.
"""

# python import
import datetime
import logging
import argparse
import sys
import time
import traceback
import json


from pyzwaver import command
from pyzwaver import zmessage
from pyzwaver import zcontroller
from pyzwaver import zdriver
from pyzwaver import znodeset
from pyzwaver import zwave

# use --logging=none
# to disable the tornado logging overrides caused by
# tornado.options.parse_command_line(
class MyFormatter(logging.Formatter):
    def __init__(self):
        pass

    TIME_FMT = '%Y-%m-%d %H:%M:%S.%f'

    def format(self, record):
        return "%s%s %s:%s:%d %s" % (
            record.levelname[0],
            datetime.datetime.fromtimestamp(record.created).strftime(MyFormatter.TIME_FMT)[:-3],
            record.threadName,
            record.filename,
            record.lineno,
            record.msg % record.args)

def main():
    global DRIVER, CONTROLLER, NODESET
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument("--verbosity", help="increase output verbosity")

    parser.add_argument('--serial_port', type=str,
                        default="/dev/ttyUSB0",
                       # default="/dev/ttyACM0",
                        help='an integer for the accumulator')

    args = parser.parse_args()
    print (args)
    # note: this makes sure we have at least one handler
    # logging.basicConfig(level=logging.WARNING)
    # logging.basicConfig(level=logging.ERROR)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # logger.setLevel(logging.ERROR)
    for h in logger.handlers:
        h.setFormatter(MyFormatter())

    logging.info("opening serial: [%s]", args.serial_port)
    device = zdriver.MakeSerialDevice(args.serial_port)

    DRIVER = zdriver.Driver(device)
    CONTROLLER = zcontroller.Controller(DRIVER, pairing_timeout_secs=60)
    CONTROLLER.Initialize()
    CONTROLLER.WaitUntilInitialized()
    CONTROLLER.UpdateRoutingInfo()
    time.sleep(2)
    print(CONTROLLER)
    NODESET = znodeset.NodeSet(DRIVER, CONTROLLER.GetNodeId())
    # n.InitializeExternally(CONTROLLER.props.product, CONTROLLER.props.library_type, True)
    logging.info("pinging %d nodes", len(CONTROLLER.nodes))
    for n in CONTROLLER.nodes:
        NODESET.Ping(n, 3, False)


    return 0


if __name__ == "__main__":
    sys.exit(main())
