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
import unittest

from pyzwaver import security


def make_bytes(s):
    out = []
    for i in range(0, len(s), 2):
        out.append(int(s[i:i + 2], 16))
    return bytes(out)


class TestSecurity2(unittest.TestCase):

    def test_basic_helpers(self):
        one_two = [int(x) for x in security.Constant15(1, 2)]
        self.assertEqual(one_two, [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])

    def test_xor(self):
        n = b"\x00" * 128
        a = b"\xa5" * 128
        b = b"\x5a" * 128
        c = b"\xff" * 128
        self.assertEqual(security.str_xor(a, a), n)
        self.assertEqual(security.str_xor(a, n), a)
        self.assertEqual(security.str_xor(a, b), c)
        self.assertEqual(security.str_xor(a, c), b)

    def test_str_inc(self):
        b = b"\x00" * 2
        for i in range(256 ** len(b) + 1):
            self.assertEqual(i % (256 ** len(b)), int.from_bytes(b, 'big'))
            b = security.str_inc(b)


# Note, the test vectors were gleaned from
# https://csrc.nist.gov/projects/cryptographic-algorithm-validation-program/random-number-generators
# also:
# https://raw.githubusercontent.com/coruus/nist-testvectors/master/csrc.nist.gov/groups/STM/cavp/documents/drbg/drbgtestvectors/drbgvectors_no_reseed/CTR_DRBG.txt
class TestCrtDrbg(unittest.TestCase):

    def test_update(self):
        empty = security.str_zero(16)
        EntropyInput = make_bytes(
            "48e8271c4b554d9da3f88c820d078f6a3f66acf007cc98840e03e26c62527f91")
        Key = make_bytes("100adbd2b12b7dfc958791d5a9e0ca30")
        V = make_bytes("3cee763e677a3b16fd2b20d513e081e9")

        key, v = security._CTR_DRBG_AES128_update(EntropyInput, empty, empty)
        self.assertEqual(key, Key)
        self.assertEqual(v, V)

    def test_generation_simple(self):
        EntropyInput = make_bytes(
            "48e8271c4b554d9da3f88c820d078f6a3f66acf007cc98840e03e26c62527f91")
        ReturnedBits = make_bytes(
            "b9a956a6e3d10310e57e287c284c6867ed9e8084a62b25c49218fa3aede7c6eaec162269"
            "6640f6b4ad5379c6fb8f9b5d7202ad89105d03173487e29da9739390")

        ctr_drbg = security.CTR_DRBG_AES128(EntropyInput)
        out = ctr_drbg.generate(64)
        out = ctr_drbg.generate(64)
        self.assertEqual(out, ReturnedBits)

    def test_generation_personality(self):
        EntropyInput = make_bytes(
            "cee23de86a69c7ef57f6e1e12bd16e35e51624226fa19597bf93ec476a44b0f2")
        PersonalizationString = make_bytes(
            "a2ef16f226ea324f23abd59d5e3c660561c25e73638fe21c87566e86a9e04c3e")

        ReturnedBits = make_bytes(
            "2a76d71b329f449c98dc08fff1d205a2fbd9e4ade120c7611c225c984eac853128"
            "8dd3049f3dc3bb3671501ab8fbf9ad49c86cce307653bd8caf29cb0cf07764")

        ctr_drbg = security.CTR_DRBG_AES128(EntropyInput, PersonalizationString)
        out = ctr_drbg.generate(64)
        out = ctr_drbg.generate(64)
        self.assertEqual(out, ReturnedBits)

    def test_generation_personality_and_additional_input(self):
        EntropyInput = make_bytes(
            "c129c2732003bbf1d1dec244a933cd04cb47199bbce98fe080a1be880afb2155")

        PersonalizationString = make_bytes(
            "64e2b9ac5c20642e3e3ee454b7463861a7e93e0dd1bbf8c4a0c28a6cb3d811ba")

        AdditionalInput1 = make_bytes(
            "f94f0975760d52f47bd490d1623a9907e4df701f601cf2d573aba803a29d2b51")

        AdditionalInput2 = make_bytes(
            "6f99720b186e2028a5fcc586b3ea518458e437ff449c7c5a318e6d13f75b5db7")

        ReturnedBits = make_bytes(
            "7b8b3378b9031ab3101cec8af5b8ba5a9ca2a9af41432cd5f2e5e19716140bb21"
            "9ed7f4ba88fc37b2d7e146037d2cac1128ffe14131c8691e581067a29cacf80")

        ctr_drbg = security.CTR_DRBG_AES128(EntropyInput, PersonalizationString)
        out = ctr_drbg.generate(64, AdditionalInput1)
        out = ctr_drbg.generate(64, AdditionalInput2)
        self.assertEqual(out, ReturnedBits)


# KEX_THIS_PUBLIC = [241, 161, 252, 183, 216, 208, 168, 168,
#                    85, 136, 232, 131, 233, 248, 27, 175,
#                    175, 58, 218, 106, 56, 8, 80, 187,
#                    69, 113, 72, 126, 172, 197, 242, 110]
#
# KEX_OTHER_PUBLIC = [98, 211, 192, 14, 139, 113, 13, 0,
#                     147, 53, 9, 161, 136, 51, 34, 50,
#                     242, 83, 191, 247, 251, 254, 105, 29,
#                     125, 85, 74, 69, 251, 137, 35, 99]
# #
# KEX_SHARED_SECRET = [159, 255, 158, 20, 229, 248, 233, 131,
#                      226, 28, 186, 214, 225, 163, 71, 95,
#                      238, 253, 59, 204, 179, 198, 243, 211,
#                      194, 254, 26, 71, 232, 45, 194, 94]

KEX_TMP_KEY = [114, 143, 34, 56, 122, 30, 54, 159, 163, 233, 0, 77, 25, 231, 62, 157]
KEX_TMP_PERSONALIZATION_STRING = [136, 226, 91, 237, 14, 154, 26, 30, 212, 130, 154, 174, 76, 240, 153, 71, 190, 15, 54, 105, 87, 163, 207, 71, 185, 71, 253, 252, 125, 232, 211, 95]

KEX_THIS_NONCE = [0, 0, 0, 0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0, 0, 0, 0]

KEX_OTHER_NODE = 25
KEX_THIS_NODE = 1

HOME_ID = [0x01, 0x84, 0xdf, 0xda]

# Security2_MessageEncapsulation
MESSAGE = [
    0x9f, 0x03, 0x06, 0x01, 0x12, 0x41, 0xfd, 0x58,
    0xe9, 0x6b, 0x58, 0xc8, 0xb3, 0x42, 0x8d, 0x57,
    0xb7, 0x06, 0x8d, 0x82, 0x77, 0x67, 0x48, 0xd3,
    0x7c, 0x06, 0x47, 0xe2, 0x35, 0xb3, 0x49, 0x8e,
    0x06, 0x4f, 0x17, 0x3c]

assert len(MESSAGE) == 36
MESSAGE_SEQ = MESSAGE[2]
assert MESSAGE_SEQ == 6

MESSAGE_PLAINTEXT = MESSAGE[3:4 + 18]
assert MESSAGE_PLAINTEXT == [1, 18, 65, 253, 88, 233, 107, 88, 200, 179, 66, 141, 87, 183, 6, 141, 130, 119, 103]

MESSAGE_CIPHER = MESSAGE[22:36]
assert MESSAGE_CIPHER == [72, 211, 124, 6, 71, 226, 53, 179, 73, 142, 6, 79, 23, 60]

MESSAGE_OTHER_NONCE = MESSAGE[6:6 + 16]
assert MESSAGE_OTHER_NONCE == [253, 88, 233, 107, 88, 200, 179, 66, 141, 87, 183, 6, 141, 130, 119, 103]


# TODO: fix this test
class TestKex(unittest.TestCase):

    def test_basic(self):
        span = security.SPAN(MESSAGE_SEQ - 1, 666, KEX_OTHER_NODE,
                             bytes(KEX_THIS_NONCE), KEX_TMP_PERSONALIZATION_STRING)
        span.AddSenderEntropy(bytes(MESSAGE_OTHER_NONCE))

        nonce = span.GetNonce()
        aad = [KEX_OTHER_NODE] + HOME_ID + [0, 36, MESSAGE_SEQ] + MESSAGE_PLAINTEXT
        print (security.Decrypt(KEX_TMP_KEY, nonce, MESSAGE_CIPHER, aad))


# @@@@@@ 16 b'\x05\xa5p\x99o\x92\xca\x85\xb4\xc2\xbf\x13\xff\xb0\x16,' 32 b"\xee>7]\x9f\x1a\x96\xc4\x13\xe5sM8Bk\x05\xbc\xfb8=\xe8\x01\xd5:A\x95'\x9a/BO\x9b"
# WARNING:root:RECEIVED [21]: Security2_NonceGet - {'seq': 205}
# WARNING:root:Sending Nonce: {'seq': 205, 'mode': 1, 'nonce': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}

# WARNING:root:RECEIVED [21]: Security2_MessageEncapsulation - {'seq': 206, 'extensions': {'mode': 1, 'extensions': [(65, [178, 48, 39, 11, 100, 24, 150, 39, 105, 254, 29, 225, 152, 192, 144, 179])], 'ciphertext': [209, 122, 176, 104, 86, 152, 253, 17, 24, 169, 105, 68, 231, 132]}}
# WARNING:root:RECEIVED [21]: Security2_MessageEncapsulation - {'seq': 207, 'extensions': {'mode': 0, 'extensions': [], 'ciphertext': [233, 14, 12, 131, 233, 112, 126, 108, 166, 55, 67, 189, 229, 214]}}
# WARNING:root:RECEIVED [21]: Security2_MessageEncapsulation - {'seq': 208, 'extensions': {'mode': 0, 'extensions': [], 'ciphertext': [6, 122, 39, 174, 153, 137, 212, 201, 237, 140, 61, 71, 236, 233]}}
# WARNING:root:RECEIVED [21]: Security2_MessageEncapsulation - {'seq': 209, 'extensions': {'mode': 0, 'extensions': [], 'ciphertext': [255, 133, 58, 58, 188, 105, 228, 212, 159, 125, 180, 44, 132, 5]}}
# WARNING:root:RECEIVED [21]: Security2_MessageEncapsulation - {'seq': 210, 'extensions': {'mode': 0, 'extensions': [], 'ciphertext': [219, 69, 33, 143, 196, 12, 124, 95, 77, 160, 255, 117, 225, 14]}}
# ^CException ignored in: <module 'threading' from '/usr/lib/python3.6/threading.py'>
# Traceback (most recent call last):
#

#  Old Security0 stuff
#
# RANDOM1 = [0xaa, 0xaa, 0xaa, 0xaa, 0xaa, 0xaa, 0xaa, 0xaa]
# RANDOM2 = [0x54, 0x2f, 0x3b, 0x2a, 0x9e, 0xcb, 0x67, 0x22]
#
# INPUT1 = [0x98, 2]
# GOLDEN1 =  [170, 170, 170, 170, 170, 170, 170, 170,
#             253, 181, 175, 84, 24, 183, 173, 31, 114, 164, 26, 33]
#
# GOLDEN2 = [0xe9, 0x6b, 0xc9, 0x90, 0x42, 0xd7, 0x45, 0xe8,
#            0x33, 0x33, 0x10, 0x5c, 0x9d, 0x14, 0x0f, 0x17,
#            0xc1, 0xfd, 0xbf, 0x33, 0xb0, 0xb0, 0xfc, 0xaa,
#            0xde, 0x02, 0xac, 0x5c, 0x18, 0xd7, 0x3f, 0x13]
#
# INPUT2 = [0x98, 0x03, 0x00, 0x85, 0x20, 0x80, 0x62, 0x4c, 0x72, 0x4e, 0x8b, 0x63, 0x86, 0xef]
#
# def match(x, y):
#     for a, b in zip(x, y):
#         assert a == b
#
#
# def _main(argv):
#     data = INPUT1
#     random = RANDOM1
#     nonce = RANDOM2
#     sub_cmd = 129
#     src_node = 1
#     dst_node = 23
#     crypter = security.Crypter([0] * 16)
#     w = crypter.Wrap(data, nonce, random, sub_cmd, src_node, dst_node)
#     #print ("wrapped", w)
#     match(w, GOLDEN1)
#     u =  crypter.Unwrap(w, nonce, sub_cmd, src_node, dst_node)
#     #print ("unwrapped", u)
#     match (u, INPUT1)
#
#     #
#     nonce = RANDOM1
#     src_node = 23
#     dst_node = 1
#     u = crypter.Unwrap(GOLDEN2, nonce, sub_cmd, src_node, dst_node)
#     #print ("unwrapped", u)
#     match(INPUT2, u)
#     print ("PASS")


if __name__ == '__main__':
    unittest.main()
