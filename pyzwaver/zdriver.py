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
zdriver.py contains the code interacting directly with serial device
"""

import logging
import serial
import threading
import time
import collections

from pyzwaver import zwave
from pyzwaver import zmessage


def MakeSerialDevice(port="/dev/ttyUSB0"):
    dev = serial.Serial(
        port=port,
        baudrate=115200,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        # blocking
        timeout=5)
    # dev.open()
    return dev


def MessageStatsString(history):
    cutoff = 0
    with_can = 0
    total_can = 0
    by_node_cnt = collections.Counter()
    by_node_can = collections.Counter()
    by_node_dur = collections.Counter()
    by_node_bad = collections.Counter()
    by_state = collections.Counter()
    sum_duration = 0
    mm = history
    if cutoff > 0:
        mm = mm[-cutoff:]
    count = len(mm)
    for m in mm:
        node = m.node
        if m.can > 0:
            with_can += 1
            total_can += m.can
            by_node_can[node] += 1
        by_state[m.state] += 1
        by_node_cnt[node] += 1
        if m.WasAborted():
            by_node_bad[node] += 1
        if m.end:
            duration = int(1000.0 * (m.end - m.start))
            by_node_dur[node] += duration
            sum_duration += duration
    out = [
        "processed: %d  with-can: %d (total can: %d) avg-time: %dms" %
        (count, with_can, total_can, sum_duration // count),
        "by state:"
    ]
    for n in sorted(by_state.keys()):
        out.append(" %-20s: %4d" % (n, by_state[n]))

    out.append("by node:")
    for n in sorted(by_node_cnt.keys()):
        out.append(" %2d: %4d (%3d) %4dms (%3d)" % (
            n, by_node_cnt[n], by_node_can[n],
            by_node_dur[n] // by_node_cnt[n], by_node_bad[n]))
    return "\n".join(out)


DO_NOTHING = "DO_NOTHING"
DO_ACK = "DO_ACK"
DO_RETRY = "DO_RETRY"
DO_PROPAGATE = "DO_PROPAGATE"


def _ProcessReceivedMessage(inflight, m):
    """
    Process a reply message
    :param m:
    :return:
    """
    # logging.debug("rx buffer: %s", buf)
    if m[0] == zwave.NAK:
        return DO_NOTHING, ""
    elif m[0] == zwave.CAN:
        if inflight is None:
            logging.error("nothing to re-send after CAN")
            return DO_NOTHING, "stray"
        logging.error("re-sending message after CAN ==== %s",
                      zmessage.PrettifyRawMessage(inflight.payload))
        return DO_RETRY, ""

    elif m[0] == zwave.ACK:
        if inflight is None:
            logging.error("nothing to re-send after ACK")
            return DO_NOTHING, "stray"
        return False, inflight.MaybeComplete(m)
    elif m[0] == zwave.SOF:
        if zmessage.Checksum(m) != zwave.SOF:
            # maybe send a CAN?
            logging.error("bad checksum")
            return DO_NOTHING, "bad-checksum"
        if m[2] == zwave.RESPONSE:
            if inflight is None:
                logging.error("nothing to re-send after RESPONSE")
                return DO_ACK, "stray"
            return DO_ACK, inflight.MaybeComplete(m)
        elif m[2] == zwave.REQUEST:
            if (m[3] == zwave.API_ZW_APPLICATION_UPDATE or
                    m[3] == zwave.API_APPLICATION_COMMAND_HANDLER):
                return DO_PROPAGATE, ""
            else:
                if inflight is None:
                    logging.error("nothing to re-send after REQUEST")
                    return DO_ACK, "stray"
                return DO_ACK, inflight.MaybeComplete(m)
        else:
            logging.error("message is neither request nor response")
            return DO_NOTHING, "bad"
    else:
        logging.error("received unknown start byte: %s", m[0])
        return DO_NOTHING, "bad-unknown-start-byte"


class Driver(object):
    """
    Driver deals sending raw Z-Wave message (arrays of bytes) to a serial
    Z-Wave stick and receiving reply message.
    It spawns to threads:

    """

    def __init__(self, serialDevice, message_queue):
        self._device = serialDevice

        self._raw_history = []
        self._history = []  # a message is copied into this once if makes it into _inflight.
        self._device_idle = True
        self._terminate = False  # True if we want to shut things down
        self._mq = message_queue
        # Make sure we flush old stuff
        self._ClearDevice()
        self._ClearDevice()

        self._tx_thread = threading.Thread(target=self._DriverSendingThread,
                                           name="DriverSend")
        self._tx_thread.start()
        self._rx_thread = threading.Thread(target=self._DriverReceivingThread,
                                           name="DriverReceive")
        self._rx_thread.start()
        self._last = None
        self._inflight = None
        self._delay = collections.defaultdict(int)

    def __str__(self):
        out = [str(self._mq),
               MessageStatsString(self._history)]
        return "\n".join(out)

    def _LogSent(self, ts, m, comment):
        self._raw_history.append((ts, True, m, comment))
        logging.warning("sent: %s", zmessage.PrettifyRawMessage(m))

    def _LogReceived(self, ts, m, comment):
        logging.warning("recv: %s", zmessage.PrettifyRawMessage(m))
        self._raw_history.append((ts, False, m, comment))

    def _RecordInflight(self, m):
        self._history.append(m)

    def GetInFlightMessage(self):
        """"
        Returns the current outbound message being processed or None.
        """
        return self._inflight

    def Terminate(self):
        """
        Terminate shuts down the driver object.

        """
        self._terminate = True
        self._mq.EnqueueMessage(zmessage.Message(None, zmessage.LowestPriority(), lambda _: None, None))
        logging.info("Driver terminated")

    def SendRaw(self, payload, comment=""):
        # if len(payload) >= 5:
        #    if self._last == payload[4]:
        #        time.sleep(SEND_DELAY_LARGE)
        #    self._last = payload[4]

        # logging.info("sending: %s", zmessage.PrettifyRawMessage(payload))
        # TODO: maybe add some delay for non-control payload: len(payload) == 0)
        self._LogSent(time.time(), payload, comment)
        self._device.write(payload)
        self._device.flush()

    def _AdjustDelay(self, node, aborted):
        if aborted:
            if self._delay[node] < 0.08:
                self._delay[node] += 0.02
        else:
            if self._delay[node] >= 0.01:
                self._delay[node] -= 0.01

    def _DriverSendingThread(self):
        """
        Forwards message from _mq to device
        """
        logging.warning("_DriverSendingThread started")
        lock = threading.Lock()
        while not self._terminate:
            inflight = self._mq.DequeueMessage()
            if inflight.payload is None:
                inflight.callback(None)
                continue
            self._inflight = inflight
            self._RecordInflight(inflight)

            inflight.Start(lock)
            time.sleep(self._delay[inflight.node])

            self.SendRaw(inflight.payload, "")
            # Now wait for this message to complete by
            # waiting for lock to get released again
            lock.acquire()
            # dynamically adjust delay per node
            self._AdjustDelay(inflight.node, inflight.WasAborted())
            self._inflight = None
            lock.release()

        logging.warning("_DriverSendingThread terminated")

    def _ClearDevice(self):
        self._device.write(zmessage.RAW_MESSAGE_NAK)
        self._device.write(zmessage.RAW_MESSAGE_NAK)
        self._device.write(zmessage.RAW_MESSAGE_NAK)
        self._device.flush()
        self._device.flushInput()
        self._device.flushOutput()

    def _DriverReceivingThread(self):
        logging.warning("_DriverReceivingThread started")
        buf = b""
        while not self._terminate:
            r = self._device.read(1)
            if not r:
                # logging.warning("received empty message/timeout")
                continue
            buf += r
            m = buf[0:1]
            if m[0] == zwave.SOF:
                # see if we have a complete message by trying to extract it
                m = zmessage.ExtracRawMessage(buf)
                if not m:
                    continue
            buf = buf[len(m):]
            ts = time.time()
            next_action, comment = _ProcessReceivedMessage(self._inflight, m)
            self._LogReceived(ts, m, comment)
            if next_action == DO_ACK:
                self.SendRaw(zmessage.RAW_MESSAGE_ACK)
            elif next_action == DO_RETRY:
                self._inflight.IncRetry()
                self.SendRaw(self._inflight.payload, "re-try")
            elif next_action == DO_PROPAGATE:
                self.SendRaw(zmessage.RAW_MESSAGE_ACK)
                self._mq.PutIncommingRawMessage(m)

    logging.warning("_DriverReceivingThread terminated")
