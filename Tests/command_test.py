#!/usr/bin/python3
# Copyright 2016 Robert Muth
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

# python imports
import logging
import sys

# local imports

from pyzwaver import command
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


def ProcessApplicationData(data):
    print("application data: ", Hexify(data))
    data = command.MaybePatchCommand(data)
    k = (data[0], data[1])
    table = z.SUBCMD_TO_PARSE_TABLE[k[0] * 256 + k[1]]
    print ("parse table: ", table)

    value = command.ParseCommand(data)
    print (value)
    data2 = command.AssembleCommand(k, value)
    print("assembled data: ", Hexify(data2))
    assert data == data2


def EqualValues(v1, v2):
    keys = set(v1.keys()) | set(v2.keys())
    for k in keys:
        if v1[k] != v2[k]:
            if k == "value" and v1[k]["_value"] == v2[k]["_value"]:
                continue
            return False
    return True


def ProcessApplicationDataSameValue(data):
    print("application data: ", Hexify(data))
    data = command.MaybePatchCommand(data)
    k = (data[0], data[1])
    table = z.SUBCMD_TO_PARSE_TABLE[k[0] * 256 + k[1]]
    print ("parse table: ", table)

    value = command.ParseCommand(data)
    print (value)
    data2 = command.AssembleCommand(k, value)
    assert data != data2
    print("assembled data: ", Hexify(data2))
    value2 = command.ParseCommand(data2)
    print(value2)
    assert EqualValues(value, value2)


def _main(argv):
    logging.basicConfig(level=logging.WARNING)
    mode = argv[0] if argv else "normal"
    for line in sys.stdin:
        if line.startswith("#"):
            continue
        token = line.split()
        if len(token) == 0:
            continue

        print()
        print("incoming: ", line[:-1])
        message = [ParseToken(t) for t in token]
        print("hex: ", Hexify(message))
        if message[0] != z.SOF:
            continue
        if message[2] != z.REQUEST:
            continue
        if message[3] != z.API_APPLICATION_COMMAND_HANDLER:
            continue
        # status = message[4]
        # node = message[5]
        size = message[6]
        data = message[7:7 + size]
        if mode == "same_value":
            ProcessApplicationDataSameValue(data)
        else:
            ProcessApplicationData(data)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
