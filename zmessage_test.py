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

def ParseToken(t):
    if t in TRANSLATE:
        return TRANSLATE[t]
    elif ":" in t:
        return int(t.split(":", 1)[1], 16)
    else:
        return int(t, 16)

def Hexify(t):
    return ["%02x" % i for i in t]


def DoAction(a, actions, value):
    if a in [command.ACTION_STORE_SENSOR,
             command.ACTION_STORE_METER,
             command.ACTION_STORE_VALUE]:
        val = command.GetValue(actions, value)
        print (a, val)
    else:
        print (a, actions, value)
        actions.clear()

def ProcessApplicationData(data):
    print ("application data: ", Hexify(data))
    new_data = znode.MaybePatchCommand(data)
    if new_data != data:
        print ("REWRITE")
        data = new_data
    value = command.ParseCommand(data)
    k = (data[0], data[1])
    if k in command.ACTIONS:
        actions = command.ACTIONS.get(k, [])[:]
        while actions:
            a = actions.pop(0)
            DoAction(a, actions, value)
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
