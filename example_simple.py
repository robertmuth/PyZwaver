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
The program will run until all Nodes have been interviewed.
The flag '--curses' enables nice rendering via curses.

Progression:
* open the device
* start the controller
* wait for controller initialization
* wait for each node to be interviewed
  (0_None -> 10_Discovered -> 20_Interviewed)
* terminate
"""

import argparse
import curses
import datetime
import logging
import random
import sys
import threading
import time

from pyzwaver.controller import Controller
from pyzwaver.driver import Driver, MakeSerialDevice, MessageStatsString
from pyzwaver.command_translator import CommandTranslator
from pyzwaver import command
from pyzwaver.node import Nodeset, NODE_STATE_NONE, NODE_STATE_DISCOVERED


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
            datetime.datetime.fromtimestamp(
                record.created).strftime(MyFormatter.TIME_FMT)[:-3],
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


class Screen(logging.Handler):

    def __init__(self, stdscr, driver, controller, nodeset):
        logging.Handler.__init__(self)
        self.activity = ""
        self.stdscr = stdscr
        self.controller = controller
        self.nodeset = nodeset
        self.driver = driver
        self.messages = []
        self.h, self.w = self.stdscr.getmaxyx()

    def emit(self, record):
        """Implements the looging api"""
        self.messages.append(record)

    def _printyx(self, y: int, x: int, lines, attr=curses.A_NORMAL):
        try:
            for line in lines:
                self.stdscr.insstr(y, x, line, attr)
                y += 1
            return len(lines)
        except Exception as e:
            raise ValueError("%d %d (%d %d)[%s]" % (
                y, x, self.h, self.w, e))

    def _titleyx(self, y: int, x: int, line, w=80):
        if len(line) < w:
            line += " " * (w - len(line))
        return self._printyx(y, x, [line], curses.A_REVERSE | curses.A_BOLD)

    def Redraw(self):

        self.stdscr.clear()
        if curses.is_term_resized(self.h, self.w):
            self.h, self.w = self.stdscr.getmaxyx()
            curses.resizeterm(self.h, self.w)

        i = 0

        i += self._titleyx(i, 0, "CONTROLLER")
        lines = str(self.controller).split("\n")
        i += self._printyx(i, 0, lines)

        def render_node(n):
            if n == self.controller.GetNodeId():
                return"node %d CONTROLLER" % n
            elif n in self.controller.failed_nodes:
                return"node %d FAILED" % n
            elif n in self.nodeset.nodes:
                node = self.nodeset.nodes[n]
                return "%s %s" % (node.Name(), node.state)
            else:
                return "Node %d  UNKNOWN" % n

        i += self._titleyx(i, 0, "NODES")
        nodes = set(self.controller.nodes) | self.nodeset.nodes.keys()
        lines = [render_node(n) for n in nodes]
        i += self._printyx(i, 0, lines)

        i += self._titleyx(i, 0, "QUEUE")
        lines = self.driver.OutQueueString().split("\n")
        i += self._printyx(i, 0, lines)

        i += self._titleyx(i, 0, "STATS")
        lines = MessageStatsString(self.driver.History()).split("\n")
        i += self._printyx(i, 0, lines)

        i = 1
        lines = [self.format(r) for r in self.messages[-self.h + 2:]]
        self._printyx(i, 81, lines)
        i += len(lines) + 1

        self.stdscr.refresh()


def InitializeDevices(stdscr, driver, controller):
    """If stdscr is not None we use curses and must not use print
        With curses the left side shows interesting info and the right
        side show loggging.
    """
    translator = CommandTranslator(driver)
    nodeset = Nodeset(translator, controller.GetNodeId())
    translator.AddListener(TestListener())
    # n.InitializeExternally(CONTROLLER.props.product, CONTROLLER.props.library_type, True)

    if stdscr:
        screen = Screen(stdscr, driver, controller, nodeset)
        logger = logging.getLogger()
        logger.handlers.clear()
        logger.addHandler(screen)
    else:
        screen = 0
    logging.info("Pinging %d nodes", len(controller.nodes))
    for n in controller.nodes:
        translator.Ping(n, 5, False, "initial")
        time.sleep(0.5)

    logging.info("Waiting for all nodes to be interviewed")
    all_nodes = set(controller.nodes)
    ready_nodes = set([controller.GetNodeId()]) | set(controller.failed_nodes)

    while len(all_nodes) > len(ready_nodes):
         # we may create new pseudo nodes
        for n in nodeset.nodes:
            all_nodes.add(n)

        by_state = {}
        for node in nodeset.nodes.values():
            if node.state not in by_state:
                by_state[node.state] = set()
            by_state[node.state].add(node.Name())

        if stdscr:
            screen.Redraw()
        else:
            for k, v in by_state.items():
                print(k, v)

        for n, node in nodeset.nodes.items():
            node = nodeset.GetNode(n)
            if node.IsInterviewed():
                ready_nodes.add(n)
            elif node.state == NODE_STATE_NONE:
                translator.Ping(n, 3, False, "undiscovered")
            elif node.state == NODE_STATE_DISCOVERED:
                if driver.OutQueueSizeForNode(
                        n) < 10 and random.randint(0, 5) == 0:
                    node.RefreshStaticValues()

        time.sleep(3.0)


def main():
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument(
        '--serial_port',
        type=str,
        default="/dev/ttyUSB0",
        help='The USB serial device representing the Z-Wave controller stick. ' +
        'Common settings are: dev/ttyUSB0, dev/ttyACM0')

    parser.add_argument('--verbosity', type=int,
                        default=logging.ERROR,
                        help='Lower numbers mean more verbosity')

    parser.add_argument(
        '--curses',
        default=False,
        action='store_true',
        help='Use curses for rendering. Make sure your terminal '
        'is at least 200 chars wide.')

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
        print(list(threading.enumerate()))
        return 1
    controller.UpdateRoutingInfo()
    time.sleep(1)
    Banner("Initialized Controller")
    print(controller)
    if args.curses:
        try:
            curses.wrapper(InitializeDevices, driver, controller)
        except Exception as e:
            Banner(str(e))
    else:
        InitializeDevices(None, driver, controller)
    driver.Terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
