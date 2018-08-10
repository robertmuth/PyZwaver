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
Simple Example

Establishes a connection to all nodes.
Does not "interview" them
"""

# python import
import datetime
import logging
import argparse
import sys
import time

from pyzwaver import controller
from pyzwaver import driver
from pyzwaver import protocol_node
from pyzwaver import zwave as z


# use --logging=none
# to disable the tornado logging overrides caused by
# tornado.options.parse_command_line(
class MyFormatter(logging.Formatter):
    def __init__(self):
        super(MyFormatter, self).__init__()

    TIME_FMT = '%Y-%m-%d %H:%M:%S.%f'

    def format(self, record):
        return "%s%s %s:%s:%d %s" % (
            record.levelname[0],
            datetime.datetime.fromtimestamp(record.created).strftime(MyFormatter.TIME_FMT)[:-3],
            record.threadName,
            record.filename,
            record.lineno,
            record.msg % record.args)


class TestListener(object):

    def __init__(self):
        self._count = 0

    def put(self, n, _, key, values):
        name = "@NONE@"
        if key[0] is not None:
            name = "%s  (%02:%02x)" % (z.SUBCMD_TO_STRING.get(key[0] * 256 + key[1]), key[0], key[1])
        logging.info("RECEIVED [%d]: %s - %s", n, name, values)
        self._count += 1


def main():
    global DRIVER, CONTROLLER, NODESET
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument("--verbosity", help="increase output verbosity")

    parser.add_argument('--serial_port', type=str,
                        default="/dev/ttyUSB0",
                        # default="/dev/ttyACM0",
                        help='an integer for the accumulator')

    args = parser.parse_args()
    print(args)
    # note: this makes sure we have at least one handler
    # logging.basicConfig(level=logging.WARNING)
    # logging.basicConfig(level=logging.ERROR)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # logger.setLevel(logging.ERROR)
    for h in logger.handlers:
        h.setFormatter(MyFormatter())

    logging.info("opening serial: [%s]", args.serial_port)
    device = driver.MakeSerialDevice(args.serial_port)

    DRIVER = driver.Driver(device)
    CONTROLLER = controller.Controller(DRIVER, pairing_timeout_secs=60)
    CONTROLLER.Initialize()
    CONTROLLER.WaitUntilInitialized()
    CONTROLLER.UpdateRoutingInfo()
    time.sleep(2)
    print(CONTROLLER)
    NODESET = protocol_node.NodeSet(DRIVER, CONTROLLER.GetNodeId())
    NODESET.AddListener(TestListener())
    # n.InitializeExternally(CONTROLLER.props.product, CONTROLLER.props.library_type, True)
    logging.info("pinging %d nodes", len(CONTROLLER.nodes))
    for n in CONTROLLER.nodes:
        node = NODESET.GetNode(n)
        node.Ping(3, False)

    time.sleep(3)
    print("Node List:")
    for n in CONTROLLER.nodes:
        print(NODESET.GetNode(n))
    DRIVER.Terminate()

    return 0


if __name__ == "__main__":
    sys.exit(main())
