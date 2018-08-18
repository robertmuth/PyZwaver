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
Example command line tool for pairing/unpairing
"""

# python import
import logging
import argparse
import sys
import time
from typing import Dict, Tuple, List

from pyzwaver.controller import Controller
from pyzwaver.driver import Driver, MakeSerialDevice
from pyzwaver import zmessage
from pyzwaver import protocol_node
from pyzwaver import zwave as z

XMIT_OPTIONS_NO_ROUTE = (z.TRANSMIT_OPTION_ACK |
                         z.TRANSMIT_OPTION_EXPLORE)

XMIT_OPTIONS = (z.TRANSMIT_OPTION_ACK |
                z.TRANSMIT_OPTION_AUTO_ROUTE |
                z.TRANSMIT_OPTION_EXPLORE)

XMIT_OPTIONS_SECURE = (z.TRANSMIT_OPTION_ACK |
                       z.TRANSMIT_OPTION_AUTO_ROUTE)


class NodeUpdateListener(object):

    def put(self, n, _ts, key, values):
        print("RECEIVED ", n, key, values)


def ControllerEventCallback(action, event):
    print(action, event)


def InitController(args, update_routing=False) -> Tuple[Driver, Controller]:
    logging.info("opening serial: [%s]", args.serial_port)
    device = MakeSerialDevice(args.serial_port)

    driver = Driver(device)
    controller = Controller(driver, pairing_timeout_secs=args.pairing_timeout_sec)
    controller.Initialize()
    controller.WaitUntilInitialized()
    if update_routing:
        controller.UpdateRoutingInfo()
        driver.WaitUntilAllPreviousMessagesHaveBeenHandled()
    print(controller.StringBasic())
    if update_routing:
        print(controller.StringRoutes())
    # print(controller.props.StringApis())
    return driver, controller


def cmd_hard_reset(args):
    driver, controller = InitController(args)
    driver.Terminate()


def cmd_pair(args):
    driver, controller = InitController(args)
    controller.StopAddNodeToNetwork(ControllerEventCallback)
    controller.AddNodeToNetwork(ControllerEventCallback)
    controller.StopAddNodeToNetwork(ControllerEventCallback)
    driver.Terminate()


def cmd_unpair(args):
    driver, controller = InitController(args)
    controller.StopRemoveNodeFromNetwork(None)
    controller.RemoveNodeFromNetwork(ControllerEventCallback)
    controller.StopRemoveNodeFromNetwork(None)
    driver.Terminate()


def cmd_hard_reset(args):
    driver, controller = InitController(args)
    controller.SetDefault()
    driver.Terminate()


def cmd_controller_details(args):
    driver, controller = InitController(args, True)
    driver.Terminate()


def cmd_set_basic_multi(args):
    driver, controller = InitController(args, True)
    nodeset = protocol_node.NodeSet(driver, controller.GetNodeId())
    nodes = [nodeset.GetNode(n) for n in args.node]
    logging.info("sending command to %s", nodes)
    nodeset.SendMultiCommand(nodes,
                             z.Basic_Set,
                             {"level": args.level},
                             zmessage.ControllerPriority(),
                             XMIT_OPTIONS
                             )

    driver.Terminate()


def cmd_get_basic(args):
    driver, controller = InitController(args, True)
    nodeset = protocol_node.NodeSet(driver, controller.GetNodeId())
    nodeset.AddListener(NodeUpdateListener())
    for n in args.node:
        node = nodeset.GetNode(n)
        node.SendCommand(z.Basic_Get,
                         {},
                         zmessage.ControllerPriority(),
                         XMIT_OPTIONS)
    time.sleep(2)
    driver.Terminate()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbosity", type=int, default=40,
                        help="increase output verbosity")

    parser.add_argument("--pairing_timeout_sec", type=int, default=30,
                        help="(un)pairing timeout")

    parser.add_argument("--serial_port", type=str, default="/dev/ttyUSB0",
                        help='The USB serial device representing the Z-Wave controller stick. '
                             'Common settings are: dev/ttyUSB0, dev/ttyACM0')

    subparsers = parser.add_subparsers(help="sub-commands")

    s = subparsers.add_parser("pair", help="Pair a Z-wave node")
    s.set_defaults(func=cmd_pair)

    s = subparsers.add_parser("unpair", help="Unpair a Z-wave node")
    s.set_defaults(func=cmd_unpair)

    s = subparsers.add_parser("hard_reset", help="Factory reset Z-wave controller")
    s.set_defaults(func=cmd_hard_reset)

    s = subparsers.add_parser("controller_details", help="Show Z-wave controller details")
    s.set_defaults(func=cmd_controller_details)

    s = subparsers.add_parser("set_basic_multi", help="Send mutlicast BasicSet command")
    s.set_defaults(func=cmd_set_basic_multi)
    s.add_argument("--level", type=int, default=99, help="level to set")
    s.add_argument('--node', type=int, nargs='+', help="dest node(s) - separate multiple nodes with spaces")

    s = subparsers.add_parser("get_basic", help="Run BasicGet command")
    s.set_defaults(func=cmd_get_basic)
    s.add_argument('--node', type=int, nargs='+', help="dest node(s) - separate multiple nodes with spaces")

    args = parser.parse_args()
    logging.basicConfig(level=args.verbosity)
    if "func" in args:
        print(args)
        args.func(args)
    else:
        # we should not reach here but there seems to be a bug
        parser.error("No command specified - try -h option")
    return 0


if __name__ == "__main__":
    sys.exit(main())
