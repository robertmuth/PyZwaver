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
Advanced Example
"""

# python import
import datetime
import logging
import argparse
import sys
import time
import signal

from pyzwaver import controller
from pyzwaver import driver
from pyzwaver import protocol_node
from pyzwaver import zwave as z
from pyzwaver import application_node


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

    def put(self, n, _, key0, key1, values):
        name = "@NONE@"
        if key0 is not None:
            name = "%s  (%02x:%02x)" % (z.SUBCMD_TO_STRING.get(key0 * 256 + key1), key0, key1)
        logging.info("RECEIVED [%d]: %s - %s", n, name, values)
        self._count += 1


def main():
    global DRIVER, CONTROLLER, PROTOCOL_NODESET, APPLICATION_NODESET

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
    #logger.setLevel(logging.INFO)
    logger.setLevel(logging.WARN)
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
    PROTOCOL_NODESET = protocol_node.NodeSet(DRIVER, CONTROLLER.GetNodeId())
    APPLICATION_NODESET = application_node.ApplicationNodeSet(PROTOCOL_NODESET)

    PROTOCOL_NODESET.AddListener(APPLICATION_NODESET)
    # n.InitializeExternally(CONTROLLER.props.product, CONTROLLER.props.library_type, True)
    logging.info("pinging %d nodes", len(CONTROLLER.nodes))

    for n in CONTROLLER.nodes:
        node = PROTOCOL_NODESET.GetNode(n)
        node.Ping(5, False)

    def signal_handler(sig, frame):
       print("Control-C pressed. Node dump:")
       for n in CONTROLLER.nodes:
           node = APPLICATION_NODESET.GetNode(n)
           print(node)
           node.RefreshStaticValues()
           node.RefreshDynamicValues()
           node.RefreshSemiStaticValues()

    signal.signal(signal.SIGINT, signal_handler)

    not_ready = CONTROLLER.nodes.copy()
    while not_ready:
        interviewed = set()
        for n in not_ready:
            node = APPLICATION_NODESET.GetNode(n)
            if node.IsInterviewed():
                    interviewed.add(node)
                    node.RefreshAssociations()
        time.sleep(2.0)
        for node in interviewed:
            print(node)
            not_ready.remove(node.n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
