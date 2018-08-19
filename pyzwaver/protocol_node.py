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

"""

import logging
import struct
import sys
import threading
import traceback
import time

from typing import List

from pyzwaver import zmessage
from pyzwaver import command
from pyzwaver import zwave as z
# from pyzwaver import zsecurity
from pyzwaver.driver import Driver


def Hexify(t):
    return ["%02x" % i for i in t]


_BAUD = [
    "unknown_baud",
    "9600_baud",
    "40000_baud",
    "100000_baud",
    "unknown_baud",
    "unknown_baud",
    "unknown_baud",
    "unknown_baud",
]


class NodeSet(object):
    """NodeSet represents the collection of all nodes in a zwave network.

    All incoming application messages from the nodes (to the controller) are arrving in the
    message_queue (_shared.mq).

    The class spawns a receiver thread, which listens to incoming messages and dispatches them
    to the node obect they are coming to.

    It also spawns a refresher Thread that will occasionally prompt nodes
    that has not been active for a while to send update requests.

    Outgoing messages from the controller to the nodes are put in the message_queue directly
    by the individual node objects.

    """

    def __init__(self, driver: Driver):
        self._driver = driver
        self._listeners = []
        self._receiver_thread = threading.Thread(target=self._NodesetReceiverThread,
                                                 name="NodeSetReceive")
        self._receiver_thread.start()

    def AddListener(self, l):
        self._listeners.append(l)

    def _PushToListeners(self, n, ts, key, value):
         for l in self._listeners:
                l.put(n, ts, key, value)

    def _SendMessageMulti(self, nn, m, priority: tuple, handler):
        mesg = zmessage.Message(m, priority, handler, nn[0])
        self._driver.SendMessage(mesg)

    def SendMultiCommand(self, nodes: List[int], key, values, priority: tuple, xmit: int):
        try:
            raw_cmd = command.AssembleCommand(key[0], key[1], values)
        except Exception as e:
            logging.error("cannot assemble command for %s %s %s",
                          command.StringifyCommand(key),
                          z.SUBCMD_TO_PARSE_TABLE[key[0] * 256 + key[1]],
                          values)
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
            return

        def handler(_):
            logging.debug("@@handler invoked")

        m = zmessage.MakeRawCommandMultiWithId(nodes, raw_cmd, xmit)
        self._SendMessageMulti(nodes, m, priority, handler)

    def _ProcessProtocolInfo(self, n, data):
        a, b, _, basic, generic, specific = struct.unpack(">BBBBBB", data)
        flags = set()
        if a & 0x80:
            flags.add("listening")
        if a & 0x40:
            flags.add("routing")
        baud = (a & 0x38) >> 3
        flags.add(_BAUD[baud])

        if b & 0x01:
            flags.add("security")
        if b & 0x02:
            flags.add("controller")
        if b & 0x04:
            flags.add("specific_device")
        if b & 0x08:
            flags.add("routing_slave")
        if b & 0x10:
            flags.add("beam_capable")
        if b & 0x20:
            flags.add("sensor_250ms")
        if b & 0x40:
            flags.add("sensor_1000ms")
        if b & 0x80:
            flags.add("optional_functionality")
        out = {
            "protocol_version":  1 + (a & 0x7),
            "flags": flags,
            "device_type": (basic, generic, specific),
        }
        self._PushToListeners(n, time.time(), command.CUSTOM_COMMAND_PROTOCOL_INFO, out)

    def _SendMessage(self, n, m, priority: tuple, handler):
        mesg = zmessage.Message(m, priority, handler, n)
        self._driver.SendMessage(mesg)

    def SendCommand(self, n, key, values, priority: tuple, xmit: int):
        try:
            raw_cmd = command.AssembleCommand(key[0], key[1], values)
        except Exception as _e:
            logging.error("cannot assemble command for %s %s %s",
                          command.StringifyCommand(key),
                          z.SUBCMD_TO_PARSE_TABLE[key[0] * 256 + key[1]],
                          values)
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
            return

        def handler(_):
            logging.debug("@@handler invoked")

        m = zmessage.MakeRawCommandWithId(n, raw_cmd, xmit)
        self._SendMessage(n, m, priority, handler)

    def _RequestNodeInfo(self, n, retries):
        """This usually triggers send "API_ZW_APPLICATION_UPDATE:"""

        def handler(_):
            # if we timeout  m will be None
            if m is not None and m[4] != 0:
                return  # success
            logging.warning("[%d] RequestNodeInfo failed: %s",
                            n, zmessage.PrettifyRawMessage(m))
            self._RequestNodeInfo(n, retries - 1)

        if retries > 0:
            logging.warning("[%d] RequestNodeInfo try:%d", n, retries)
            m = zmessage.MakeRawMessage(z.API_ZW_REQUEST_NODE_INFO, [n])
            self._SendMessage(n, m, zmessage.ControllerPriority(), handler)

        else:
            logging.error("[%d] RequestNodeInfo failed permanently", n)

    def GetNodeProtocolInfo(self, n):
        def handler(message):
            if not message:
                logging.error("ProtocolInfo failed")
                return
            payload = message[4:-1]
            if len(payload) < 5:
                logging.error("bad ProtocolInfo payload: %s", message)
                return
            self._ProcessProtocolInfo(n, payload)

        logging.warning("[%d] GetNodeProtocolInfo", n)
        m = zmessage.MakeRawMessage(z.API_ZW_GET_NODE_PROTOCOL_INFO, [n])
        self._SendMessage(n, m, zmessage.ControllerPriority(), handler)

    def _UpdateIsFailedNode(self, n, cb):

        def handler(m):
            if m is None:
                return
            logging.info("[%d] is failed check: %d, %s", n,
                         m[4], zmessage.PrettifyRawMessage(m))
            failed = m[4] != 0
            self._PushToListeners(n, time.time(), command.CUSTOM_COMMAND_FAILED_NODE, {"failed": failed})
            if cb:
                cb(failed)

        m = zmessage.MakeRawMessage(z.API_ZW_IS_FAILED_NODE_ID, [n])
        self._SendMessage(n, m, zmessage.ControllerPriority(), handler)

    def Ping(self, n, retries, force):
        logging.warning("[%d] Ping retries %d, force: %s", n, retries, force)

        self.GetNodeProtocolInfo(n)
        if force:
            self._UpdateIsFailedNode(n, None)
            self._RequestNodeInfo(n, retries)
        else:
            def handler(failed):
                if not failed:
                    self._RequestNodeInfo(n, retries)

            self._UpdateIsFailedNode(n, handler)

    def _HandleMessageApplicationCommand(self, ts, m):
        _ = m[4]  # status
        n = m[5]
        size = m[6]
        try:
            data = [int(x) for x in m[7:7 + size]]
            data = command.MaybePatchCommand(data)
            value = command.ParseCommand(data)
            if value is None:
                logging.error("[%d] parsing failed for %s", n, Hexify(data))
                return
        except Exception as _e:
            logging.error("[%d] cannot parse: %s", n, zmessage.PrettifyRawMessage(m))
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
            return

        self._PushToListeners(n, ts, (data[0], data[1]), value)

    def _HandleMessageApplicationUpdate(self, ts, m):
        kind = m[4]
        if kind == z.UPDATE_STATE_NODE_INFO_REQ_FAILED:
            n = m[5]
            if n != 0:
                logging.error(
                    "update request failed: %s", zmessage.PrettifyRawMessage(m))
        elif kind == z.UPDATE_STATE_NODE_INFO_RECEIVED:
            # the node is awake now and/or has changed values
            n = m[5]
            length = m[6]
            m = m[7: 7 + length]
            commands = []
            controls = []
            seen_marker = False
            for i in m[3:]:
                if i == z.Mark:
                    seen_marker = True
                elif seen_marker:
                    controls.append(i)
                else:
                    commands.append(i)
            value = {
                "type": (m[0], m[1], m[2]),
                "commands": commands,
                "controls": controls,
            }
            self._PushToListeners(n, ts, command.CUSTOM_COMMAND_APPLICATION_UPDATE, value)

        elif kind == z.UPDATE_STATE_SUC_ID:
            logging.warning("succ id updated: needs work")
        else:
            logging.error("unknown kind: %x", kind)
            assert False

    def _NodesetReceiverThread(self):
        logging.warning("_NodesetReceiverThread started")
        while True:
            ts, m = self._driver.GetIncommingRawMessage()
            if m is None:
                break
            if m[3] == z.API_APPLICATION_COMMAND_HANDLER:
                self._HandleMessageApplicationCommand(ts, m)
            elif m[3] == z.API_ZW_APPLICATION_UPDATE:
                self._HandleMessageApplicationUpdate(ts, m)
            else:
                logging.error("unhandled message: %s", zmessage.PrettifyRawMessage(m))
        logging.warning("_NodesetReceiverThread terminated")
