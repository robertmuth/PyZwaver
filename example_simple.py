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
Simple example demonstrating basic pyzwaver concepts.

Progression:
* open the device
* start the controller
* wait for controller initialization
* wait for each node to be interviewed
* terminate
"""

# python import
import datetime
import logging
import argparse
import sys
import time

from pyzwaver.controller import Controller
from pyzwaver.driver import Driver, MakeSerialDevice
from pyzwaver.command_translator import CommandTranslator
from pyzwaver import command
from pyzwaver.node import Nodeset

def _NodeName(n):
    return str(n) if n <= 255 else "%d.%d" % (n >> 8, n & 0xff)

class MyFormatter(logging.Formatter):
    """
    Nicer logging format
    """

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
    """
    Demonstrates how to hook into the stream of messages
    sent to the controller from other nodes
    """

    def __init__(self):
        pass

    def put(self, n, ts, key, values):
        name = "@NONE@"
        if key[0] is not None:
            name = command.StringifyCommand(key)
        logging.warning("RECEIVED [%s]: %s - %s", _NodeName(n), name, values)


def Banner(m):
    print("=" * 60)
    print(m)
    print("=" * 60)


def main():
    global driver, controller, translator, nodeset

    parser = argparse.ArgumentParser(description='Process some integers.')

    parser.add_argument('--serial_port', type=str,
                        default="/dev/ttyUSB0",
                        help='The USB serial device representing the Z-Wave controller stick. ' +
                             'Common settings are: dev/ttyUSB0, dev/ttyACM0')

    parser.add_argument('--verbosity', type=int,
                        default=30,
                        help='Lower numbers mean more verbosity')

    args = parser.parse_args()
    # note: this makes sure we have at least one handler
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger()
    logger.setLevel(args.verbosity)
    for h in logger.handlers:
        h.setFormatter(MyFormatter())

    logging.info("opening serial: [%s]", args.serial_port)
    device = MakeSerialDevice(args.serial_port)

    driver = Driver(device)
    controller = Controller(driver, pairing_timeout_secs=60)
    controller.Initialize()
    success = controller.WaitUntilInitialized(2)
    if not success:
        logging.error("could not initialize controller")
        driver.Terminate()
        print (list(threading.enumerate()))
        return 1
    controller.UpdateRoutingInfo()
    time.sleep(2)
    Banner("Initialized Controller")
    print(controller)

    translator = CommandTranslator(driver)
    nodeset = Nodeset(translator, controller.GetNodeId())
    translator.AddListener(TestListener())
    # n.InitializeExternally(CONTROLLER.props.product, CONTROLLER.props.library_type, True)

    logging.info("Pinging %d nodes", len(controller.nodes))
    for n in controller.nodes:
        translator.Ping(n, 5, False, "initial")
        time.sleep(0.5)

    logging.info("Waiting for all nodes to be interviewed")
    all_nodes = set(controller.nodes)
    ready_nodes = set([controller.GetNodeId()])
    time.sleep(2.0)
    for n in nodeset.nodes: all_nodes.add(n)
    print ("all nodes so far: %s" % repr(all_nodes))
    while len(all_nodes) != len(ready_nodes):
        for n in nodeset.nodes: all_nodes.add(n)
        not_ready = all_nodes - ready_nodes
        print("\nStill waiting for %s" % str(not_ready))
        for n in not_ready:
            node = nodeset.GetNode(n)
            if node.IsInterviewed():
                ready_nodes.add(node.n)
                Banner("Interviewed Node %s" % node.Name())
                print (node)
            elif node.IsFailed():
                ready_nodes.add(node.n)
            else:
                node.RefreshStaticValues()

        time.sleep(2.0)
    driver.Terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
