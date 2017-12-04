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
zmessage_test.py represents a simple testing tool for the parsing/processing
of API_APPLICATION_COMMAND messages.
It reads a textual representation of the full messages from stdin.
One message per line starting with SOF and ending woth the checksum.
The processed result and action is printed to stdout.

"""

import logging
import sys

from pyzwaver import zwave
from pyzwaver import command
from pyzwaver import znode

TRANSLATE = {
    "SOF": zwave.SOF,
    "REQU": zwave.REQUEST,
    "RESP": zwave.RESPONSE,
}

class FakeMulti:
    def _init__(self):
        pass

    def StoreCount(self, v):
        print ("StoreCount: ", v)

    def Set(self, v):
        print ("Set: ", v)

    def SetVersion(self, v):
        print ("SetVersion: ", v)

    def SetSupported(self, v):
        print ("SetSupported: ", v)

    def StoreNodes(self, v):
        print ("StoreNodes: ", v)


class FakeNode:
    def __init__(self):
        self._sensors = FakeMulti()
        self._meters = FakeMulti()
        self._associations = FakeMulti()
        self._commands = FakeMulti()
        self._parameters = FakeMulti()

    def StoreValue(self, v):
        print ("StoreValue: ", v)


def ParseToken(t):
    if t in TRANSLATE:
        return TRANSLATE[t]
    elif ":" in t:
        return int(t.split(":", 1)[1], 16)
    else:
        return int(t, 16)

def Hexify(t):
    return ["%02x" % i for i in t]



def ProcessApplicationData(data):
    print ("application data: ", Hexify(data))
    new_data = znode.MaybePatchCommand(data)
    if new_data != data:
        print ("REWRITE")
        data = new_data
    value = command.ParseCommand(data, "")
    k = (data[0], data[1])
    node = FakeNode()
    if k in command.ACTIONS:
        func, num_val, event = command.ACTIONS.get(k)
        func(node, value, k, "")

    else:
        print("ERROR", k)
        sys.exit(1)

def _main(argv):
    logging.basicConfig(level=logging.ERROR)
    for line in sys.stdin:
        if line.startswith("#"): continue
        token = line.split()
        if len(token) == 0: continue

        print ()
        print ("incoming: ", line[:-1])
        message = [ParseToken(t) for t  in token]
        print ("hex: ", message)
        if message[0] != zwave.SOF: continue
        if message[2] != zwave.REQUEST: continue
        if message[3] != zwave.API_APPLICATION_COMMAND_HANDLER: continue
        #status = message[4]
        #node = message[5]
        size = message[6]
        data = message[7:7 + size]
        ProcessApplicationData(data)

if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
