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

import logging
import sys

from pyzwaver import zsecurity

RANDOM1 = [0xaa, 0xaa, 0xaa, 0xaa, 0xaa, 0xaa, 0xaa, 0xaa]
RANDOM2 = [0x54, 0x2f, 0x3b, 0x2a, 0x9e, 0xcb, 0x67, 0x22]

INPUT1 = [0x98, 2]
GOLDEN1 =  [170, 170, 170, 170, 170, 170, 170, 170,
            253, 181, 175, 84, 24, 183, 173, 31, 114, 164, 26, 33]

GOLDEN2 = [0xe9, 0x6b, 0xc9, 0x90, 0x42, 0xd7, 0x45, 0xe8,
           0x33, 0x33, 0x10, 0x5c, 0x9d, 0x14, 0x0f, 0x17,
           0xc1, 0xfd, 0xbf, 0x33, 0xb0, 0xb0, 0xfc, 0xaa,
           0xde, 0x02, 0xac, 0x5c, 0x18, 0xd7, 0x3f, 0x13]

INPUT2 = [0x98, 0x03, 0x00, 0x85, 0x20, 0x80, 0x62, 0x4c, 0x72, 0x4e, 0x8b, 0x63, 0x86, 0xef]

def match(x, y):
    for a, b in zip(x, y):
        assert a == b


def _main(argv):
    data = INPUT1
    random = RANDOM1
    nonce = RANDOM2
    sub_cmd = 129
    src_node = 1
    dst_node = 23
    crypter = zsecurity.Crypter([0] * 16)
    w = crypter.Wrap(data, nonce, random, sub_cmd, src_node, dst_node)
    #print ("wrapped", w)
    match(w, GOLDEN1)
    u =  crypter.Unwrap(w, nonce, sub_cmd, src_node, dst_node)
    #print ("unwrapped", u)
    match (u, INPUT1)

    #
    nonce = RANDOM1
    src_node = 23
    dst_node = 1
    u = crypter.Unwrap(GOLDEN2, nonce, sub_cmd, src_node, dst_node)
    #print ("unwrapped", u)
    match(INPUT2, u)
    print ("PASS")

if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
