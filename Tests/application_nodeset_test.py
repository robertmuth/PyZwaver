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
Example command line tool for pairing/unpairing
"""

# python import
import logging
import sys
from typing import Dict, Tuple, List
import queue

from pyzwaver import zmessage
from pyzwaver.command_translator import CommandTranslator
from pyzwaver.node import Nodeset, Node
from pyzwaver import zwave as z


class FakeDriver(object):

    def __init__(self):
        self.history = []

    def AddListener(self, l):
        pass

    def SendMessage(self, m: zmessage.Message):
        self.history.append(m)
        print(m)


def main():
    fake_driver = FakeDriver()
    translator = CommandTranslator(fake_driver)
    nodeset = Nodeset(translator, 1)

    node = nodeset.GetNode(2)

    assert not node.values.HasCommandClass(z.Basic)
    node.put(0, z.Version_CommandClassReport, {"class": z.Basic, "version": 10})
    assert node.values.HasCommandClass(z.Basic)

    print ("OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
