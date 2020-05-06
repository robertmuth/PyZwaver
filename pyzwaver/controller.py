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
controller.py contains code for dealing with the controller node in a zwave network.
"""

import logging
import struct
import time

from pyzwaver import zmessage
from pyzwaver import zwave as z
from pyzwaver.driver import Driver

_APPLICATION_NODEINFO_LISTENING = 1
_NUM_NODE_BITFIELD_BYTES = 29

MESSAGE_TIMEOUT = 100
MESSAGE_NOT_DELIVERED = 101

CONTROLLER_STATE_NONE = 0
CONTROLLER_STATE_INITIALIZED = 1

ACTIVITY_ADD_NODE = "AddNode"
ACTIVITY_STOP_ADD_NODE = "StopAddNode"
ACTIVITY_REMOVE_NODE = "RemoveNode"
ACTIVITY_SET_LEARN_MODE = "SetLearnMode"
ACTIVITY_CHANGE_CONTROLLER = "ChangeController"
ACTIVITY_CONTROLLER_UPDATE = "ControllerUpdate"

EVENT_PAIRING_ABORTED = "Aborted"
EVENT_PAIRING_CONTINUE = "InProgress"
EVENT_PAIRING_FAILED = "Failed"
EVENT_PAIRING_SUCCESS = "Success"
EVENT_PAIRING_STARTED = "Started"

EVENT_UPDATE_STARTED = "Started"
EVENT_UPDATE_COMPLETE = "Complete"


def ExtractNodes(bits):
    assert len(bits) == _NUM_NODE_BITFIELD_BYTES
    r = set()
    for i in range(8 * _NUM_NODE_BITFIELD_BYTES):
        if (bits[i // 8] & (1 << (i % 8))) == 0:
            continue
        node_id = i + 1
        r.add(node_id)
    return r


PAIRING_ACTION_CONTINUE = 1
PAIRING_ACTION_DONE = 2
PAIRING_ACTION_FAILED = 3
PAIRING_ACTION_DONE_UPDATE = 4

HANDLER_TYPE_ADD_NODE = (z.ADD_NODE_STATUS_TO_STRING, {
    z.ADD_NODE_STATUS_LEARN_READY: PAIRING_ACTION_CONTINUE,
    z.ADD_NODE_STATUS_ADDING_SLAVE: PAIRING_ACTION_CONTINUE,
    z.ADD_NODE_STATUS_ADDING_CONTROLLER: PAIRING_ACTION_CONTINUE,
    z.ADD_NODE_STATUS_NODE_FOUND: PAIRING_ACTION_CONTINUE,

    z.ADD_NODE_STATUS_FAILED: PAIRING_ACTION_FAILED,
    z.REMOVE_NODE_STATUS_NOT_INCLUSION_CONTROLLER: PAIRING_ACTION_FAILED,

    z.ADD_NODE_STATUS_DONE: PAIRING_ACTION_DONE_UPDATE,
    z.ADD_NODE_STATUS_PROTOCOL_DONE: PAIRING_ACTION_DONE_UPDATE,
})

HANDLER_TYPE_STOP = (z.ADD_NODE_STATUS_TO_STRING, {
    z.ADD_NODE_STATUS_LEARN_READY: PAIRING_ACTION_CONTINUE,
    z.ADD_NODE_STATUS_ADDING_SLAVE: PAIRING_ACTION_CONTINUE,
    z.ADD_NODE_STATUS_ADDING_CONTROLLER: PAIRING_ACTION_CONTINUE,
    z.ADD_NODE_STATUS_NODE_FOUND: PAIRING_ACTION_CONTINUE,

    z.ADD_NODE_STATUS_FAILED: PAIRING_ACTION_DONE,
    z.REMOVE_NODE_STATUS_NOT_INCLUSION_CONTROLLER: PAIRING_ACTION_DONE,

    z.ADD_NODE_STATUS_DONE: PAIRING_ACTION_DONE,
    z.ADD_NODE_STATUS_PROTOCOL_DONE: PAIRING_ACTION_DONE,
})

HANDLER_TYPE_REMOVE_NODE = (z.REMOVE_NODE_STATUS_TO_STRING, {
    z.REMOVE_NODE_STATUS_LEARN_READY: PAIRING_ACTION_CONTINUE,
    z.REMOVE_NODE_STATUS_REMOVING_SLAVE: PAIRING_ACTION_CONTINUE,
    z.REMOVE_NODE_STATUS_NODE_FOUND: PAIRING_ACTION_CONTINUE,
    z.REMOVE_NODE_STATUS_NOT_INCLUSION_CONTROLLER: PAIRING_ACTION_FAILED,
    z.REMOVE_NODE_STATUS_FAILED: PAIRING_ACTION_FAILED,
    z.REMOVE_NODE_STATUS_DONE: PAIRING_ACTION_DONE_UPDATE,
    z.REMOVE_NODE_STATUS_REMOVING_CONTROLLER: PAIRING_ACTION_CONTINUE,
})

HANDLER_TYPE_SET_LEARN_MODE = (z.LEARN_MODE_STATUS_TO_STRING, {
    z.LEARN_MODE_STATUS_STARTED: PAIRING_ACTION_CONTINUE,
    z.LEARN_MODE_STATUS_FAILED: PAIRING_ACTION_FAILED,
    z.LEARN_MODE_STATUS_DONE: PAIRING_ACTION_DONE_UPDATE,
})


class ControllerProperties:

    def __init__(self):
        self.home_id = None
        self.node_id = None
        self.product = [0, 0, 0]
        self.chip_type = None
        self.version = None
        self.version_str = None
        self.serial_api_version = None
        self.serial_version = None
        self.library_type = None
        self._api_mask = None
        self.attrs = set()

    def SetVersion(self, version_str, library_type):
        if version_str[-1] == 0:
            version_str = version_str[:-1]

        self.library_type = library_type
        self.version_str = version_str
        assert self.library_type <= 8
        if self.library_type == 7:
            self.attrs.add("bridge")
        logging.info("library_type: %s", self.library_type)

    def SetId(self, home_id, node_id):
        self.home_id = home_id
        self.node_id = node_id
        logging.info("home-id: 0x%x node-id: %d", self.home_id, self.node_id)

    def SetControllerCapabilites(self, caps):
        logging.info("capabilities: %x", caps)
        if caps & z.CAP_CONTROLLER_SECONDARY:
            self.attrs.add("secondary")
        if caps & z.CAP_CONTROLLER_SUC:
            self.attrs.add("suc")
        if caps & z.CAP_CONTROLLER_SIS:
            self.attrs.add("sis")
        if caps & z.CAP_CONTROLLER_REAL_PRIMARY:
            self.attrs.add("real_primary")

    def HasApi(self, func):
        fid = func - 1
        return self._api_mask[fid // 8] & (1 << (fid % 8))

    def SetSerialCapabilities(
            self,
            serial_api_version,
            manu_id,
            type_id,
            prod_id,
            api_mask):
        self.serial_api_version = serial_api_version
        self.product = (manu_id, type_id, prod_id)
        self._api_mask = api_mask

    def SetInitAndReturnBits(
            self,
            serial_version,
            caps,
            num_bytes,
            bits,
            chip_type,
            version):
        assert num_bytes == _NUM_NODE_BITFIELD_BYTES
        self.serial_version = serial_version
        self.chip_type = chip_type
        self.version = version
        logging.info("serial caps: %x", caps)
        if caps & z.SERIAL_CAP_SLAVE:
            self.attrs.add("serial_slave")
        if caps & z.SERIAL_CAP_TIMER_SUPPORT:
            self.attrs.add("serial_timer")
        if caps & z.SERIAL_CAP_SECONDARY:
            self.attrs.add("serial_secondary")
        return bits

    def StringApis(self):
        out = []
        for func, name in z.API_TO_STRING.items():
            if self.HasApi(func):
                out.append("%s[%d]" % (name, func))
        return "\n".join(out)

    def __str__(self):
        out = [
            "home: %08x  node: %02x" %
            (self.home_id,
             self.node_id),
            "versions: %s %x %x (%s)" %
            (self.version,
             self.serial_api_version,
             self.serial_version,
             self.version_str),
            "chip: %x.%02x" %
            (self.chip_type,
             self.version),
            "product: %04x %04x %04x  %x" %
            (self.product[0],
             self.product[1],
             self.product[2],
             self.library_type),
            "attrs: %s" %
            repr(
                self.attrs)]
        return "\n".join(out)


class Controller:
    """Represents the controller node in a Zwave network
    The message_queue is used to send messages to the physical controller and
    the other nodes in the network.


    """

    def __init__(self, message_queue: Driver, pairing_timeout_secs=15.0):
        """
        :param message_queue:  is used to send commands to the controller and other zwave nodes.
                               The other end of the queue must be handled by the driver.
        :param pairing_timeout_secs:
        """
        # self._event_cb = event_cb
        self._pairing_timeout_sec = pairing_timeout_secs
        self._state = CONTROLLER_STATE_NONE
        self._mq = message_queue
        self.nodes = set()
        self.failed_nodes = set()
        self.props = ControllerProperties()
        self.routes = {}

    def __str__(self):
        out = [
            self.StringBasic(),
            "",
            self.StringRoutes(),
        ]
        return "\n".join(out)

    @classmethod
    def Priority(cls):
        return zmessage.ControllerPriority()

    def StringBasic(self):
        return "\n".join([
            str(self.props),
            "nodes: %s" % repr(self.nodes),
            "failed_nodes: %s" % repr(self.failed_nodes)])

    def StringRoutes(self):
        out = []
        nodes = sorted(self.nodes)
        for n in nodes:
            line = "%2d: " % n
            routes = self.routes.get(n, set())
            for m in nodes:
                if m in routes:
                    line += "#"
                else:
                    line += " "
            out.append(line)
        return "\n".join(out)

    def UpdateVersion(self):
        def handler(data):
            if not data:
                # logging.error("Cannot read controller version. Check serial device.")
                raise ValueError(
                    "Cannot read controller version. Check serial device.")
            else:
                self.props.SetVersion(*struct.unpack(">12sB", data[4:-1]))

        self.SendCommand(z.API_ZW_GET_VERSION, [], handler)

    def UpdateId(self):
        def handler(data):
            self.props.SetId(*struct.unpack(">IB", data[4:-1]))

        self.SendCommand(z.API_ZW_MEMORY_GET_ID, [], handler)

    def UpdateControllerCapabilities(self):
        def handler(data):
            self.props.SetControllerCapabilites(data[4])

        self.SendCommand(z.API_ZW_GET_CONTROLLER_CAPABILITIES, [], handler)

    def UpdateSerialApiGetCapabilities(self):
        """
        """

        def handler(data):
            self.props.SetSerialCapabilities(
                *struct.unpack(">HHHH32s", data[4:-1]))

        self.SendCommand(z.API_SERIAL_API_GET_CAPABILITIES, [], handler)

    def UpdateSerialApiGetInitData(self):
        """This get all the node numbers"""

        def handler(data):
            bits = self.props.SetInitAndReturnBits(
                *struct.unpack(">BBB29sBB", data[4:-1]))
            self.nodes = ExtractNodes(bits)

        self.SendCommand(z.API_SERIAL_API_GET_INIT_DATA, [], handler)

    def SetTimeouts(self, ack_timeout_msec, byte_timeout_msec):
        def handler(data):
            logging.info(
                "previous timeouts: %d %d",
                data[4] * 10,
                data[5] * 10)

        self.SendCommand(z.API_SERIAL_API_SET_TIMEOUTS,
                         [ack_timeout_msec // 10, byte_timeout_msec // 10],
                         handler)

    def UpdateSucNodeId(self):
        def handler(data):
            succ_node = data[4]
            logging.info("suc node id: %s", succ_node)

        self.SendCommand(z.API_ZW_GET_SUC_NODE_ID, [], handler)

    def GetRandom(self, _, cb):
        def handler(data):
            success = data[4]
            size = data[5]
            data = data[6:6 + size]
            cb(success, data)

        self.SendCommand(z.API_ZW_GET_RANDOM, [], handler)

    def UpdateFailedNode(self, node: int):
        def handler(data):
            if data[4]:
                self.failed_nodes.add(node)
            else:
                self.failed_nodes.discard(node)

        self.SendCommand(z.API_ZW_IS_FAILED_NODE_ID, [node], handler)

    def ReadMemory(self, offset: int, length: int, cb):
        def handler(data, _):
            data = data[4: -1]
            logging.info("received %x bytes", len(data))
            cb(data)

        self.SendCommand(z.API_ZW_READ_MEMORY,
                         [offset >> 8, offset & 0xff, length],
                         handler)

    def GetRoutingInfo(self, node: int, rem_bad, rem_non_repeaters, cb):
        def handler(data):
            cb(node, ExtractNodes(data[4:-1]))

        self.SendCommand(z.API_ZW_GET_ROUTING_INFO,
                         [node, rem_bad, rem_non_repeaters, 3],
                         handler)

    def SetPromiscuousMode(self, state):
        def handler(_):
            pass

        self.SendCommand(z.API_ZW_SET_PROMISCUOUS_MODE, [state], handler)

    def RequestNodeInfo(self, node: int, cb=None):
        """Force the generation of a zwave.API_ZW_APPLICATION_UPDATE event
        """
        logging.warning("requesting node info for %d", node)

        def handler(data):
            if cb:
                cb(data[4])

        self.SendCommand(z.API_ZW_REQUEST_NODE_INFO, [node], handler)

    def RemoveFailedNode(self, node: int, cb):
        def handler(m):
            if not m:
                cb(MESSAGE_TIMEOUT)
            elif m[2] == z.RESPONSE:
                cb(MESSAGE_NOT_DELIVERED)
            else:
                return cb(m[5])

        self.SendCommandWithId(
            z.API_ZW_REMOVE_FAILED_NODE_ID, [node], handler)

    # ============================================================
    # Routing
    # ============================================================
    def UpdateRoutingInfo(self):
        def handler(node, neighbors):
            logging.info("[%d] setting routing info to: %s", node, neighbors)
            self.routes[node] = set(neighbors)

        for n in self.nodes:
            self.GetRoutingInfo(n, False, False, handler)

    # ============================================================
    # Pairing
    # ============================================================
    def MakeFancyReceiver(self, activity: str, receiver_type, event_cb):
        stringMap, actions = receiver_type

        def Handler(m):
            if m is None:
                logging.error("[%s] Aborted", activity)
                event_cb(activity, EVENT_PAIRING_ABORTED, None)
                return True
            if not m:
                event_cb(activity, EVENT_PAIRING_STARTED, None)
                return True

            status = m[5]
            node = m[6]
            name = stringMap[status]
            a = actions[status]
            logging.warning("pairing status update: %s", a)
            if a == PAIRING_ACTION_CONTINUE:
                logging.warning(
                    "[%s] Continue - %s [%d]", activity, name, node)
                event_cb(activity, EVENT_PAIRING_CONTINUE, node)
                return False
            elif a == PAIRING_ACTION_DONE:
                logging.warning("[%s] Success", node)
                event_cb(activity, EVENT_PAIRING_SUCCESS, node)
                return True

            elif a == PAIRING_ACTION_DONE_UPDATE:
                logging.warning(
                    "[%s] Success - updating nodes %s [%d]",
                    activity,
                    name,
                    node)
                event_cb(activity, EVENT_PAIRING_SUCCESS, node)
                # This not make much sense for node removals but does not hurt
                # either
                self.RequestNodeInfo(node)
                self.Update(None)
                return True
            elif a == PAIRING_ACTION_FAILED:
                logging.warning("[%s] Failure - %s [%d]", activity, name, node)
                event_cb(activity, EVENT_PAIRING_FAILED, node)
                return True
            else:
                logging.error("activity unexpected: ${name}")
                return False

        return Handler

    def NeighborUpdate(self, node: int, event_cb):
        activity = "NeighborUpdate",

        def Handler(m):
            if m is None:
                logging.error("[%s] Aborted", activity)
                event_cb(activity, EVENT_PAIRING_ABORTED, node)
                return True
            if not m:
                event_cb(activity, EVENT_PAIRING_STARTED, node)
                return False

            status = m[5]
            if status == z.REQUEST_NEIGHBOR_UPDATE_STARTED:
                event_cb(activity, EVENT_PAIRING_CONTINUE, node)
                return False
            elif status == z.REQUEST_NEIGHBOR_UPDATE_DONE:
                event_cb(activity, EVENT_PAIRING_SUCCESS, node)
                return True
            elif status == z.REQUEST_NEIGHBOR_UPDATE_FAIL:
                event_cb(activity, EVENT_PAIRING_FAILED, node)
                return True
            else:
                logging.error(
                    "[%s] unknown status %d %s",
                    activity,
                    status,
                    zmessage.Hexify(m))
                return True

        logging.warning("NeighborUpdate(%d)", node)
        return self.SendCommandWithId(z.API_ZW_REQUEST_NODE_NEIGHBOR_UPDATE, [
                                      node], Handler, timeout=self._pairing_timeout_sec)

    def AddNodeToNetwork(self, event_cb):
        logging.warning("AddNodeToNetwork")
        mode = [z.ADD_NODE_ANY]
        cb = self.MakeFancyReceiver(
            ACTIVITY_ADD_NODE,
            HANDLER_TYPE_ADD_NODE,
            event_cb)
        return self.SendCommandWithId(z.API_ZW_ADD_NODE_TO_NETWORK, mode, cb,
                                      timeout=self._pairing_timeout_sec)

    def StopAddNodeToNetwork(self, event_cb):
        logging.warning("StopAddNodeToNetwork")
        mode = [z.ADD_NODE_STOP]
        cb = self.MakeFancyReceiver(
            ACTIVITY_STOP_ADD_NODE,
            HANDLER_TYPE_STOP,
            event_cb)
        return self.SendCommandWithId(z.API_ZW_ADD_NODE_TO_NETWORK, mode, cb,
                                      timeout=5)

    def RemoveNodeFromNetwork(self, event_cb):
        logging.warning("RemoveNodeFromNetwork")
        mode = [z.REMOVE_NODE_ANY]
        cb = self.MakeFancyReceiver(
            ACTIVITY_REMOVE_NODE,
            HANDLER_TYPE_REMOVE_NODE,
            event_cb)
        return self.SendCommandWithId(
            z.API_ZW_REMOVE_NODE_FROM_NETWORK,
            mode,
            cb,
            timeout=self._pairing_timeout_sec)

    def StopRemoveNodeFromNetwork(self, _):
        mode = [z.REMOVE_NODE_STOP]
        # NOTE: this will sometimes result in a "stray request" being sent back:
        #  SOF len:07 REQU API_ZW_REMOVE_NODE_FROM_NETWORK:4b cb:64 status:06 00 00 chk:d1
        # We just drop this message on the floor
        return self.SendCommandWithIdNoResponse(
            z.API_ZW_REMOVE_NODE_FROM_NETWORK, mode)

    def SetLearnMode(self, event_cb):
        mode = [z.LEARN_MODE_NWI]
        cb = self.MakeFancyReceiver(
            ACTIVITY_SET_LEARN_MODE,
            HANDLER_TYPE_SET_LEARN_MODE,
            event_cb)
        return self.SendCommandWithId(
            z.API_ZW_SET_LEARN_MODE,
            mode,
            cb,
            timeout=self._pairing_timeout_sec)

    def StopSetLearnMode(self, _):
        mode = [z.LEARN_MODE_DISABLE]
        return self.SendCommandWithIdNoResponse(z.API_ZW_SET_LEARN_MODE, mode)

    def ChangeController(self, event_cb):
        mode = [z.CONTROLLER_CHANGE_START]
        cb = self.MakeFancyReceiver(
            ACTIVITY_CHANGE_CONTROLLER,
            HANDLER_TYPE_ADD_NODE,
            event_cb)
        return self.SendCommandWithId(
            z.API_ZW_CONTROLLER_CHANGE,
            mode,
            cb,
            timeout=self._pairing_timeout_sec)

    def StopChangeController(self, _):
        mode = [z.CONTROLLER_CHANGE_STOP]
        return self.SendCommandWithIdNoResponse(
            z.API_ZW_CONTROLLER_CHANGE, mode)

    # ============================================================
    # ============================================================
    def ApplNodeInformation(self):
        """Advertise/change the features of this node"""

        def handler(_):
            logging.warning("controller is now initialized")
            self._state = CONTROLLER_STATE_INITIALIZED

        self.SendCommand(z.API_SERIAL_API_APPL_NODE_INFORMATION,
                         [_APPLICATION_NODEINFO_LISTENING,
                          2,  # generic
                          1,  # specific
                          0,  # rest: size + data
                          ],
                         handler)

    def SendNodeInformation(self, dst_node: int, xmit: int, cb):
        def handler(message):
            cb(message[4:-1])

        self.SendCommandWithId(z.API_ZW_SEND_NODE_INFORMATION,
                               [dst_node, xmit],
                               handler)

    def SetDefault(self):
        """Factory reset the controller"""

        def handler(message):
            if message:
                message = message[4:-1]
            logging.warning("set default response %s", message)

        self.SendCommandWithId(z.API_ZW_SET_DEFAULT, [], handler)

    def SoftReset(self):
        def handler(message):
            if message:
                message = message[4:-1]
            logging.warning("soft reset response %s", message)

        self.SendCommandWithId(z.API_SERIAL_API_SOFT_RESET, [], handler)

    def SendCommand(self, func, data, handler):
        raw = zmessage.MakeRawMessage(func, data)
        mesg = zmessage.Message(raw, self.Priority(), handler, -1)
        self._mq.SendMessage(mesg)

    def SendCommandWithId(self, func, data, handler, timeout=2.0):
        raw = zmessage.MakeRawMessageWithId(func, data)
        mesg = zmessage.Message(
            raw, self.Priority(), handler, -1, timeout=timeout)
        self._mq.SendMessage(mesg)

    def SendCommandWithIdNoResponse(self, func, data, timeout=2.0):
        raw = zmessage.MakeRawMessageWithId(func, data)
        mesg = zmessage.Message(
            raw, self.Priority(), None, -1, timeout=timeout, action_requ=[
                zmessage.ACTION_NONE], action_resp=[
                zmessage.ACTION_NONE])
        self._mq.SendMessage(mesg)

    def SendBarrierCommand(self, handler):
        """Dummy Command to invoke the handler when all previous commands are done"""
        logging.warning("SendBarrierCommand")
        mesg = zmessage.Message(None, self.Priority(), handler, None)
        self._mq.SendMessage(mesg)

    def Initialize(self):
        self.UpdateVersion()
        self.UpdateId()
        self.UpdateControllerCapabilities()
        self.UpdateSerialApiGetCapabilities()
        self.UpdateSerialApiGetInitData()
        self.SetTimeouts(1000, 150)
        self.UpdateSucNodeId()
        # promotes controller to "INITIALIZED"
        self.ApplNodeInformation()

    def WaitUntilInitialized(self, max_wait=2):
        logging.info("Controller::WaitUntilInitialized")
        deadline = time.time() + max_wait
        while self._state != CONTROLLER_STATE_INITIALIZED:
            logging.warning(
                "wait - current Controller state is: %s",
                self._state)
            time.sleep(0.5)
            if time.time() > deadline:
                return False
        return True

    def TriggerNodesUpdate(self):
        logging.info("trigger nodes update")
        for n in self.nodes:
            if n == self.props.node_id:
                continue
            self.RequestNodeInfo(n)

    def GetNodeId(self):
        return self.props.node_id

    def Update(self, cb):
        logging.warning("Update")
        # self._event_cb(ACTIVITY_CONTROLLER_UPDATE, EVENT_UPDATE_STARTED)
        self.UpdateId()
        self.UpdateControllerCapabilities()
        self.UpdateSerialApiGetCapabilities()
        self.UpdateSerialApiGetInitData()
        for n in self.nodes:
            self.UpdateFailedNode(n)
        self.SendBarrierCommand(cb)
