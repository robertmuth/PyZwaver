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
znode_test.py represents a simple testing tool for the parsing/processing
of API_APPLICATION_COMMAND via the node/nodeset classes.
It reads a textual representation of the full messages from stdin.
One message per line starting with SOF and ending woth the checksum.
The processed result and action is printed to stdout.

"""

import logging
import sys
import queue

from pyzwaver import zmessage
from pyzwaver.command_translator import CommandTranslator
from pyzwaver.node import Nodeset, NodeValues
from pyzwaver import zwave as z

TRANSLATE = {
    "SOF": z.SOF,
    "REQU": z.REQUEST,
    "RESP": z.RESPONSE,
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


class FakeDriver(object):

    def __init__(self):
        self.history = []

    def GetIncommingRawMessage(self):
        return self.in_queue.get()

    def SendMessage(self, m: zmessage.Message):
        self.history.append(m)
        print(m)

    def AddListener(self, l):
        pass

def Banner(m):
    print("=" * 60)
    print(m)
    print("=" * 60)


def _main(argv):
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)

    fake_driver = FakeDriver()
    translator = CommandTranslator(fake_driver)
    nodeset = Nodeset(translator, 1)
    ts = 0
    for line in sys.stdin:
        ts += 1
        if line.startswith("#"): continue
        token = line.split()
        if len(token) == 0: continue

        print()
        print("incoming: ", line[:-1])
        mesg = [ParseToken(t) for t in token]
        print("hex: ", Hexify(mesg))
        translator.put(ts, mesg)

    for n in nodeset.nodes.values():
        Banner("Node %s" % n.n)
        values: NodeValues = n.values
        print("########### VALUES")
        for v in sorted(values.Values()):
            print(v)
        print("########### VERSIONS")
        for v in sorted(values.CommandVersions()):
            print(v)
        print("########### CONFIGURATIONS")
        for v in sorted(values.Configuration()):
            print(v)
        print("########### ASSOCIATIONS")
        for v in sorted(values.Associations()):
            print(v)
        print("########### METERS")
        for v in sorted(values.Meters()):
            print(v)
        print("########### SENSORS")
        for v in sorted(values.Sensors()):
            print(v)

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
