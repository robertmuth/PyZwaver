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
from typing import Dict, Tuple, List

from pyzwaver.controller import Controller
from pyzwaver.driver import Driver, MakeSerialDevice
from pyzwaver import protocol_node
from pyzwaver import zwave as z

def ControllerEventCallback(action, event):
    print (action, event)


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
    print(controller)
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

    args = parser.parse_args()
    logging.basicConfig(level=args.verbosity)
    args.func(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
