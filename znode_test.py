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

from pyzwaver import zwave
from pyzwaver import znode
from pyzwaver import zmessage

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

def dummy_cb(a, b):
    pass

def _main(argv):
    logger = logging.getLogger()
    logger.setLevel(logging.ERROR)
    MQ =  zmessage.MessageQueue()
    NODESET = znode.NodeSet(MQ, event_cb=dummy_cb, refresher_interval=0)
    for line in sys.stdin:
        if line.startswith("#"): continue
        token = line.split()
        if len(token) == 0: continue

        print ()
        print ("incoming: ", line[:-1])
        mesg = [ParseToken(t) for t  in token]
        print ("hex: ", mesg)
        MQ.PutIncommingRawMessage(mesg)

    NODESET.Terminate()
    for n in NODESET.AllNodes():
        print(n)

if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
