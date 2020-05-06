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
zmessage.py contains helpers for message encoding and the business logic
that decides when a message has been properly processed.
"""

import collections
import logging
import threading
import time

from pyzwaver import zwave as z


# ==================================================
# Priorities for outgoing messages
# ==================================================


def ControllerPriority():
    return 1, 0, -1


def NodePriorityHi(node: int) -> tuple:
    return 2, 0, node


def NodePriorityLo(node: int) -> tuple:
    return 3, 0, node


def LowestPriority() -> tuple:
    return 1000, 0, -1


# ==================================================
# Raw Messages
# ==================================================

_CB_ID_COUNTER = 66


def CallbackId():
    global _CB_ID_COUNTER
    _CB_ID_COUNTER += 1
    _CB_ID_COUNTER %= 256
    return _CB_ID_COUNTER


def Checksum(data):
    checksum = 0xff
    for b in data:
        checksum = checksum ^ b
    return checksum


def Hexify(t):
    return ["%02x" % i for i in t]


def PrettifyRawMessage(m):
    if m is None:
        return "None"
    out = Hexify(m)
    if len(m) <= 2:
        return " ".join(out)
    out[0] = z.FIRST_TO_STRING.get(m[0], "??")
    if m[0] != z.SOF:
        return " ".join(out)
    out[1] = "len:" + out[1]
    if m[2] == z.REQUEST:
        out[2] = "REQU"
    if m[2] == z.RESPONSE:
        out[2] = "RESP"
    out[-1] = "chk:" + out[-1]
    func = m[3]
    if func in z.API_TO_STRING:
        out[3] = z.API_TO_STRING[func] + ":" + out[3]
    if func == z.API_ZW_APPLICATION_UPDATE and len(m) > 5:
        out[5] = "node:" + out[5]
        if m[2] == z.REQUEST:
            out[4] = z.UPDATE_STATE_TO_STRING[m[4]]
    elif func == z.API_APPLICATION_COMMAND_HANDLER and len(m) > 8:
        out[6] = "len:" + out[6]
        out[5] = "node:" + out[5]
        s = z.SUBCMD_TO_STRING.get(m[7] * 256 + m[8])
        if s:
            out[7] = s + ":" + out[7]
            out[8] = "X:" + out[8]
        else:
            logging.error("did not find command %s %s  [%s]", m[7], m[8], m)

    elif (func == z.API_ZW_ADD_NODE_TO_NETWORK or
          func == z.API_ZW_REMOVE_NODE_FROM_NETWORK or
          func == z.API_ZW_SET_LEARN_MODE) and len(m) > 7:

        if len(m) == 7:
            # sednding
            out[4] = "kind:" + out[4]
            out[5] = "cb:" + out[5]
        else:
            # receiving
            out[4] = "cb:" + out[4]
            out[5] = "status:" + out[5]
    elif (func == z.API_ZW_REQUEST_NODE_INFO or
          func == z.API_ZW_GET_NODE_PROTOCOL_INFO or
          func == z.API_ZW_GET_ROUTING_INFO or
          func == z.API_ZW_IS_FAILED_NODE_ID) and len(m) > 4:
        if m[2] == z.REQUEST and len(out) > 4:
            out[4] = "node:" + out[4]
    elif func == z.API_ZW_ADD_NODE_TO_NETWORK:
        out[4] = z.ADD_NODE_TO_STRING[m[4]]
    elif (func == z.API_ZW_SEND_DATA or
          func == z.API_ZW_REPLICATION_SEND_DATA) and len(m) > 7:
        if m[2] == z.REQUEST:
            if len(m) == 7 or len(m) == 9:
                out[4] = "cb:" + out[4]
                out[5] = "status:" + out[5]
            else:
                out[4] = "node:" + out[4]
                out[-2] = "cb:" + out[-2]
                out[-3] = "xmit:" + out[-3]
                s = z.SUBCMD_TO_STRING.get(m[6] * 256 + m[7])
                if s:
                    out[6] = s + ":" + out[6]
                    out[7] = "X:" + out[7]
                else:
                    logging.error(
                        "did not find command (send (repl.)data) %s %s [%s]",
                        m[6], m[7], m)

    return " ".join(out)


def RawMessageFuncId(data):
    return data[-2]


def RawMessageDstNode(data):
    if len(data) < 5:
        return -1
    if data[3] == z.API_ZW_SEND_DATA:
        return data[4]
    return -1


def RawMessageIsRequest(data):
    if len(data) < 5:
        return -1
    return data[2] == z.REQUEST


def RawMessageCommandType(data):
    if len(data) < 5:
        return -1
    return data[3]


def ExtracRawMessage(data):
    if len(data) < 5:
        return None
    if data[0] != z.SOF:
        return None
    length = data[1]
    # +2: includes the SOF byte and the length byte
    if len(data) < length + 2:
        return None
    return data[0:length + 2]


# ==================================================

def MakeRawMessage(func, data):
    out = [z.SOF, len(data) + 3, z.REQUEST, func] + data
    # check sum over everything except the first byte
    out.append(Checksum(out) ^ z.SOF)
    return bytes(out)


def MakeRawMessageWithId(func, data, cb_id=None):
    if cb_id is None:
        cb_id = CallbackId()
    out = [z.SOF, len(data) + 4, z.REQUEST, func] + data + [cb_id]
    # check sum over everything except the first byte
    out.append(Checksum(out) ^ z.SOF)
    return bytes(out)


def MakeRawCommandWithId(node, data, xmit, cb_id=None):
    out = [node, len(data)] + data + [xmit]
    return MakeRawMessageWithId(z.API_ZW_SEND_DATA, out, cb_id)


def MakeRawReplicationCommandWithId(node, data, xmit, cb_id=None):
    out = [node, len(data)] + data + [xmit]
    return MakeRawMessageWithId(z.API_ZW_REPLICATION_SEND_DATA, out, cb_id)


def MakeRawCommandMultiWithId(nodes, data, xmit, cb_id=None):
    out = [len(nodes)] + nodes + [len(data)] + data + [xmit]
    return MakeRawMessageWithId(z.API_ZW_SEND_DATA_MULTI, out, cb_id)


def MakeRawCommand(node, data, xmit):
    out = [node, len(data)] + data + [xmit]
    return MakeRawMessage(z.API_ZW_SEND_DATA, out)


def MakeRawReplicationSendDataWithId(node, data, xmit, cb_id=None):
    out = [node, len(data)] + data + [xmit]
    return MakeRawMessageWithId(z.API_ZW_REPLICATION_SEND_DATA, out, cb_id)


RAW_MESSAGE_ACK = bytes([z.ACK])
RAW_MESSAGE_NAK = bytes([z.NAK])
RAW_MESSAGE_CAN = bytes([z.CAN])

# ==================================================
# Message
# ==================================================

MESSAGE_STATE_CREATED = "Created"
MESSAGE_STATE_STARTED = "Started"
MESSAGE_STATE_COMPLETED = "Completed"
MESSAGE_STATE_ABORTED = "Aborted"
MESSAGE_STATE_TIMEOUT = "Timeout"
MESSAGE_STATE_NOT_READY = "NotReady"

MESSAGE_STATES_FINAL = {
    MESSAGE_STATE_COMPLETED,
    MESSAGE_STATE_NOT_READY,
    MESSAGE_STATE_ABORTED,
    MESSAGE_STATE_TIMEOUT
}

# TODO: explain these in detail
ACTION_INVALID = 0
ACTION_DELIVERED = 1
ACTION_DONE = 3
ACTION_NONE = 4
ACTION_REPORT_NE = 5
ACTION_REPORT = 6
ACTION_MATCH_CBID_MULTI = 7
ACTION_MATCH_CBID = 8
ACTION_NO_REPORT = 9
ACTION_REPORT_EQ = 10

# maps inflight message type to the action taken when a matching response
# is received
_RESPONSE_ACTION = {
    z.API_ZW_REMOVE_FAILED_NODE_ID: [ACTION_REPORT_EQ, 0],  # removal started
    z.API_ZW_SET_DEFAULT: [ACTION_NONE],
}

_REQUEST_ACTION = {
    z.API_ZW_REMOVE_FAILED_NODE_ID: [ACTION_MATCH_CBID, 7],
    z.API_ZW_SET_DEFAULT: [ACTION_MATCH_CBID, 6],
}

_COMMANDS_WITH_NO_ACTION = [
    z.API_SERIAL_API_APPL_NODE_INFORMATION,
    z.API_ZW_SET_PROMISCUOUS_MODE,
]

for x in _COMMANDS_WITH_NO_ACTION:
    _RESPONSE_ACTION[x] = [ACTION_NONE]
    _REQUEST_ACTION[x] = [ACTION_NONE]

_COMMANDS_WITH_RESPONSE_ACTION_REPORT = [
    z.API_ZW_GET_SUC_NODE_ID,
    z.API_ZW_GET_VERSION,
    z.API_ZW_MEMORY_GET_ID,
    z.API_ZW_GET_CONTROLLER_CAPABILITIES,
    z.API_SERIAL_API_GET_CAPABILITIES,
    z.API_ZW_GET_RANDOM,
    z.API_SERIAL_API_GET_INIT_DATA,
    z.API_SERIAL_API_SET_TIMEOUTS,
    z.API_ZW_GET_NODE_PROTOCOL_INFO,
    z.API_ZW_IS_FAILED_NODE_ID,
    z.API_ZW_GET_ROUTING_INFO,
    z.API_ZW_READ_MEMORY,
    z.API_SERIAL_API_SOFT_RESET,
    z.API_ZW_ENABLE_SUC,
    z.API_ZW_SET_SUC_NODE_ID,
    z.API_ZW_REQUEST_NODE_INFO,
]

for x in _COMMANDS_WITH_RESPONSE_ACTION_REPORT:
    _RESPONSE_ACTION[x] = [ACTION_REPORT]
    _REQUEST_ACTION[x] = [ACTION_NONE]

_COMMANDS_WITH_SIMPLE_RESPONSE_AND_REQUEST = {
    z.API_ZW_SEND_DATA: [7, 9],
    z.API_ZW_SEND_DATA_MULTI: [7],
    z.API_ZW_SEND_NODE_INFORMATION: [7],
    z.API_ZW_REPLICATION_SEND_DATA: [7],
}

for x, y in _COMMANDS_WITH_SIMPLE_RESPONSE_AND_REQUEST.items():
    _RESPONSE_ACTION[x] = [ACTION_REPORT_EQ, 1]
    _REQUEST_ACTION[x] = [ACTION_MATCH_CBID] + y

_COMMANDS_WITH_MULTI_REQUESTS = [
    z.API_ZW_ADD_NODE_TO_NETWORK,
    z.API_ZW_REMOVE_NODE_FROM_NETWORK,
    z.API_ZW_CONTROLLER_CHANGE,
    z.API_ZW_SET_LEARN_MODE,
    z.API_ZW_REQUEST_NODE_NEIGHBOR_UPDATE,
]

for x in _COMMANDS_WITH_MULTI_REQUESTS:
    _RESPONSE_ACTION[x] = [ACTION_NONE]
    _REQUEST_ACTION[x] = [ACTION_MATCH_CBID_MULTI]


# TODO
# RESPONSE
# zwave.API_ZW_SET_SUC_NODE_ID: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_DELETE_SUC_RETURN_ROUTE: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_REPLACE_FAILED_NODE: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_DELETE_RETURN_ROUTE: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_ASSIGN_RETURN_ROUTE: [ACTION_REPORT_NE, -1],

# zwave.API_ZW_SEND_SLAVE_NODE_INFO: [ACTION_REPORT_NE, -1],

# zwave.API_ZW_SEND_NODE_INFORMATION: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_REQUEST_NETWORK_UPDATE: [ACTION_REPORT_NE, -1],

# REQUEST
# zwave.API_ZW_SET_SUC_NODE_ID: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_DELETE_SUC_RETURN_ROUTE: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_REQUEST_NODE_INFO: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_REPLACE_FAILED_NODE: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_DELETE_RETURN_ROUTE: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_ASSIGN_RETURN_ROUTE: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_SEND_SLAVE_NODE_INFO: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_SEND_NODE_INFORMATION: [ACTION_REPORT_NE, -1],
# zwave.API_ZW_REQUEST_NETWORK_UPDATE: [ACTION_REPORT_NE, -1],


class Message:
    """Message describes and outgoing message and the actions/callbacks used to determine
    when it has been fully processed.

    """

    def __init__(self, payload, priority: tuple, callback, node,
                 timeout=1.0, action_requ=None, action_resp=None):
        self.payload = payload
        self.priority = priority
        self.node = node
        self._callback = callback
        self.timeout = timeout
        self.start = None
        self.end = None
        self.can = 0
        self.state = MESSAGE_STATE_CREATED
        self.action_requ = action_requ
        self.action_resp = action_resp
        if payload is None:
            return
        func = payload[3]
        # mode = payload[4]
        if action_requ is None:
            self.action_requ = _REQUEST_ACTION[func]
        if action_resp is None:
            self.action_resp = _RESPONSE_ACTION[func]

    def Start(self, ts):
        self.state = MESSAGE_STATE_STARTED
        self.start = ts
        if self.action_requ and self.action_requ[0] == ACTION_MATCH_CBID_MULTI:
            logging.warning("Multi request command started")
            # empty list means start, None means abort
            self._callback([])

    def WasAborted(self):
        return (self.state in MESSAGE_STATES_FINAL and
                self.state != MESSAGE_STATE_COMPLETED)

    def _CompleteNoMessage(self, ts, state):
        assert state in MESSAGE_STATES_FINAL
        self.state = state
        self.end = ts
        if state == MESSAGE_STATE_TIMEOUT:
            logging.error("%s: %s", state, PrettifyRawMessage(self.payload))
        else:
            logging.info("%s: %s", state, PrettifyRawMessage(self.payload))
        return state

    def Complete(self, ts, m, state):
        if self._callback:
            self._callback(m)
        return self._CompleteNoMessage(ts, state)

    def MaybeCompleteAck(self, ts, m):
        if (self.action_requ[0] == ACTION_NONE and
                self.action_resp[0] == ACTION_NONE):
            self.Complete(ts, m, MESSAGE_STATE_COMPLETED)
        else:
            return ""

    def MaybeCompleteRequest(self, ts, m):
        func = self.payload[3]
        if m[3] != func:
            logging.error("[%d %s unexpected request/response: %s",
                          self.node, PrettifyRawMessage(self.payload),
                          PrettifyRawMessage(m))
            return "unexpected"

        cbid = self.payload[-2]
        if self.action_requ[0] == ACTION_MATCH_CBID_MULTI:
            if m[4] != cbid:
                logging.error("[%d] %s unexpected call back id: %s",
                              self.node, PrettifyRawMessage(self.payload),
                              PrettifyRawMessage(m))
                return "unexpected"
            assert self._callback is not None
            if not self._callback(m):
                return "Continue"
            return self._CompleteNoMessage(ts, MESSAGE_STATE_COMPLETED)
        elif self.action_requ[0] == ACTION_MATCH_CBID:
            if m[4] != cbid:
                logging.error("[%d] %s unexpected call back id: %s",
                              self.node, PrettifyRawMessage(self.payload),
                              PrettifyRawMessage(m))
                return "Unexpected"
            return self.Complete(ts, m, MESSAGE_STATE_COMPLETED)

        else:
            logging.error(
                "unexpected action: %s for %s",
                self.action_requ[0],
                PrettifyRawMessage(
                    self.payload))
            assert False

    def MaybeCompleteResponse(self, ts, m):
        func = self.payload[3]
        if m[3] != func:
            logging.error("[%d %s unexpected request/response: %s",
                          self.node, PrettifyRawMessage(self.payload),
                          PrettifyRawMessage(m))
            return "unexpected"

        if self.action_resp[0] == ACTION_REPORT:
            return self.Complete(ts, m, MESSAGE_STATE_COMPLETED)
        elif self.action_resp[0] == ACTION_REPORT_EQ:
            assert len(m) == 6
            # we expect a message of the form:
            # SOF <len> RES  <func> <status> <checksum>
            if self.action_resp[1] == m[4]:
                # we got the expected status everything is dandy
                # but still need to wait for the matching req
                # Note, we currently do not record having received m
                # as we have not seen failure modes requiring it.
                logging.debug("delivered to stack")
                if self._callback:
                    self._callback(m)
                return "Continue"
            else:
                logging.error("[%d] %s unexpected resp status is %d wanted %d",
                              self.node, PrettifyRawMessage(self.payload),
                              m[4], self.action_resp[1])

                return self.Complete(ts, m, MESSAGE_STATE_NOT_READY)
        else:
            logging.error(self.action_resp[0], PrettifyRawMessage(m))
            assert False

    def __str__(self):
        out = [PrettifyRawMessage(self.payload), ]
        if self.start and not self.end:
            out.append(" running for %dms" %
                       int(1000.0 * (time.time() - self.start)))
        return " ".join(out)

    def __lt__(self, other):
        return self.priority < other.priority


# Next actions
DO_NOTHING = "DO_NOTHING"
DO_ACK = "DO_ACK"
DO_RETRY = "DO_RETRY"
DO_PROPAGATE = "DO_PROPAGATE"


class InflightMessage:
    """
    Manages the single message that may be in-flight
    """

    def __init__(self):
        self._message: Message = None
        self._timeout_thread: threading.Timer = None
        self._delay = collections.defaultdict(int)
        # this lock controls all accesses to the instance
        self._lock = threading.Lock()
        # this lock control whether there is an active instance
        self._message_lock = threading.Lock()

    def GetMessage(self) -> Message:
        with self._lock:
            return self._message

    def _Timeout(self):
        with self._lock:
            if self._message is None:
                return
            logging.error(
                "message timeout: %s",
                PrettifyRawMessage(
                    self._message.payload))
            self._message.Complete(time.time(), None, MESSAGE_STATE_TIMEOUT)
            self._message_lock.release()

    def StartMessage(self, message: Message, ts: float):
        self._message_lock.acquire()
        with self._lock:
            assert self._message is None
            message.Start(ts)
            if message.payload is None:
                logging.warning("received empty message")
                message.Complete(ts, None, MESSAGE_STATE_COMPLETED)
                self._message_lock.release()
                return False
            self._message = message
            self._timeout_thread = threading.Timer(
                message.timeout, self._Timeout)
            self._timeout_thread.start()
            time.sleep(self._delay[message.node])
            return True

    def WaitForMessageCompletion(self):
        self._message_lock.acquire()
        self._timeout_thread.cancel()
        with self._lock:
            assert self._message is not None
            node = self._message.node
            if self._message.WasAborted():
                if self._delay[node] < 0.08:
                    self._delay[node] += 0.02
            else:
                if self._delay[node] >= 0.01:
                    self._delay[node] -= 0.01
        self._message = None
        self._message_lock.release()

    def NextActionForReceivedMessage(self, ts: float, received):
        with self._lock:
            message: Message = self._message
            if received[0] == z.NAK:
                return DO_NOTHING, ""
            elif received[0] == z.CAN:
                if message is None:
                    logging.error("nothing to re-send after CAN")
                    return DO_NOTHING, "stray"
                logging.error("re-sending message after CAN ==== %s",
                              PrettifyRawMessage(message.payload))
                message.can += 1
                # does this help?
                time.sleep(0.01)
                return DO_RETRY, ""
            elif received[0] == z.ACK:
                if message is None:
                    logging.error("nothing to re-send after ACK")
                    return DO_NOTHING, "stray"
                text = message.MaybeCompleteAck(ts, received)
                if message.state in MESSAGE_STATES_FINAL:
                    self._message_lock.release()
                return DO_NOTHING, text
            elif received[0] != z.SOF:
                logging.error("received unknown start byte: %s", received[0])
                return DO_NOTHING, "bad-unknown-start-byte"

            if Checksum(received) != z.SOF:
                # maybe send a CAN?
                logging.error("bad checksum")
                return DO_NOTHING, "bad-checksum"

            if received[2] == z.RESPONSE:
                if message is None:
                    logging.error("nothing to re-send after RESPONSE")
                    return DO_ACK, "stray"
                text = message.MaybeCompleteResponse(ts, received)
                if message.state in MESSAGE_STATES_FINAL:
                    self._message_lock.release()
                return DO_ACK, text
            elif received[2] == z.REQUEST:
                if (received[3] == z.API_ZW_APPLICATION_UPDATE or
                        received[3] == z.API_APPLICATION_COMMAND_HANDLER):
                    return DO_PROPAGATE, ""
                else:
                    if message is None:
                        logging.error("nothing to re-send after REQUEST")
                        return DO_ACK, "stray"
                    text = message.MaybeCompleteRequest(ts, received)
                    if message.state in MESSAGE_STATES_FINAL:
                        self._message_lock.release()
                    return DO_ACK, text
            else:
                logging.error("message is neither request nor response")
                return DO_NOTHING, "bad"
