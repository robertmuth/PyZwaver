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

"""

import logging

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import cmac
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESCCM


def CKDF_GenerateSharedSecret(other_public_key: bytes):
    """ return shared_secret, this_public_key_bytes"""
    this_private_key_obj = X25519PrivateKey.generate()
    other_public_key_obj = X25519PublicKey.from_public_bytes(other_public_key)
    return (this_private_key_obj.exchange(other_public_key_obj),
            this_private_key_obj.public_key().public_bytes())


def CMAC(key: bytes, data: bytes):
    c = cmac.CMAC(algorithms.AES(key), backend=default_backend())
    c.update(data)
    return c.finalize()


def CKDF_TempExtract(shared_secret: bytes,
                     this_public_key: bytes,
                     other_public_key: bytes):
    return CMAC(
        bytes(
            [0x33] *
            16),
        shared_secret +
        this_public_key +
        other_public_key)


def Constant15(a, b):
    return bytes([a] * 15 + [b])


def CKDF_TempExpand(prk: bytes):
    t1 = CMAC(prk, Constant15(0x88, 1))
    t2 = CMAC(prk, t1 + Constant15(0x88, 2))
    t3 = CMAC(prk, t2 + Constant15(0x88, 3))
    return t1, t2 + t3


def CKFD_SharedKey(other_public_key: bytes):
    shared_secret, this_public_key = CKDF_GenerateSharedSecret(
        other_public_key)
    prk = CKDF_TempExtract(shared_secret, this_public_key, other_public_key)
    key_ccm, personalization_string = CKDF_TempExpand(prk)
    print("this public", [int(x) for x in this_public_key])
    print("other public", [int(x) for x in other_public_key])
    print("shared secret", [int(x) for x in shared_secret])
    print("key", [int(x) for x in key_ccm])
    print("personalization string", [int(x) for x in personalization_string])
    return key_ccm, personalization_string, this_public_key


def CKDF_MeiExtract(sender_ei: bytes, receiver_ei: bytes):
    return CMAC(bytes([0x26] * 16), sender_ei + receiver_ei)


def CKDF_MeiExpand(nonce_prk: bytes):
    t0 = Constant15(0x88, 1)
    t1 = CMAC(nonce_prk, t0 + Constant15(0x88, 1))
    t2 = CMAC(nonce_prk, t1 + Constant15(0x88, 2))
    return t1 + t2


def str_xor(a, b):
    aa = int.from_bytes(a, 'little')
    bb = int.from_bytes(b, 'little')
    return (aa ^ bb).to_bytes(len(a), 'little')


def str_pad(b, length, pad_byte=b"\x00"):
    delta = length - len(b)
    if delta < 0:
        return b
    return pad_byte * delta + b


def str_inc(b):
    lst = [int(x) for x in b]
    for i in reversed(range(0, len(b))):
        lst[i] = (lst[i] + 1) % 256
        if lst[i] != 0:
            break
    return bytes(lst)


def str_zero(length):
    return b"\x00" * length


def _CTR_DRBG_AES128_update(data, key, v):
    assert len(data) == 32
    assert len(key) == 16
    assert len(v) == 16
    cipher = Cipher(algorithms.AES(key), modes.CBC(str_zero(16)),
                    backend=default_backend())

    v = str_inc(v)
    encryptor = cipher.encryptor()
    new_key = encryptor.update(v) + encryptor.finalize()

    v = str_inc(v)
    encryptor = cipher.encryptor()
    new_v = encryptor.update(v) + encryptor.finalize()
    return str_xor(new_key, data[:16]), str_xor(new_v, data[16:])


# Counter mode Deterministic Random Byte Generator
# Specialized for SPAN based on NIST 800-90A
class CTR_DRBG_AES128(object):

    def __init__(self, entropy: bytes, personalization_string: bytes = str_zero(32)):
        assert len(entropy) == 32
        self._key, self._v = _CTR_DRBG_AES128_update(
            str_xor(entropy, personalization_string), str_zero(16), str_zero(16))

    def generate(self, count, data=None):
        out = b""
        v = self._v
        key = self._key
        if data is not None:
            key, v = _CTR_DRBG_AES128_update(data, key, v)
        cipher = Cipher(algorithms.AES(key), modes.CBC(str_zero(16)),
                        backend=default_backend())

        while len(out) < count:
            encryptor = cipher.encryptor()
            v = str_inc(v)
            out += encryptor.update(v) + encryptor.finalize()
        if data is None:
            data = str_zero(32)
        self._key, self._v = _CTR_DRBG_AES128_update(data, key, v)
        return out[:count]


class SPAN(object):

    def __init__(self, seq_no, key_type, peer_node, receiver_entropy,
                 personalization_string):
        self._seq_no = seq_no
        self.key_type = key_type
        self.peer_node = peer_node
        self._receiver_entropy = receiver_entropy
        self._personalization_string = personalization_string
        self._ctr_drbg = None

    def AddSenderEntropy(self, sender_entropy):
        nonce_prk = CKDF_MeiExtract(sender_entropy, self._receiver_entropy)
        mei = CKDF_MeiExpand(nonce_prk)
        self._ctr_drbg = CTR_DRBG_AES128(mei, self._personalization_string)

    def GetNonce(self):
        return self._ctr_drbg.generate(13)


def Encrypt(key_ccm, nonce, data, aad):
    aesccm = AESCCM(key_ccm, 8)
    return aesccm.encrypt(nonce, data, aad)


def Decrypt(key_ccm, nonce, ct, aad):
    aesccm = AESCCM(bytes(key_ccm), 8)
    return aesccm.decrypt(bytes(nonce), bytes(ct), bytes(aad))

# Old Security0 stuff
#
# from Crypto.Cipher import AES
#
# from pyzwaver import command
# from pyzwaver import z
#
# _DEFAULT_NETWORK_KEY = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
#
# _TEMP_NETWORK_KEY = [0] * 16
#
# _CRYPT_SECRET = [0xaa] * 16
#
# _AUTH_SECRET = [0x55] * 16
#
# _NONCE_TIMEOUT_SEC = 5.0
#
# _NONCE_GET_RAW = [z.Security, z.Security_NonceGet]
#
#
# def Crypt(key, data, iv_orig):
#     assert len(iv_orig) == 16
#     iv = bytes(iv_orig)
#     cipher = AES.new(bytes(key))
#     out = [0] * len(data)
#     for i in range(len(data)):
#         if i % 16 == 0:
#             iv = cipher.encrypt(iv)
#         out[i] = data[i] ^ iv[i % 16]
#     return out
#
#
# def ComputeMAC(key, data, iv, sub_command, src_node, dst_node):
#     assert len(iv) == 16
#     padding = [0] * 16
#     header = [sub_command, src_node, dst_node, len(data)]
#     buf = header + data + padding
#     cipher = AES.new(bytes(key))
#
#     auth = list(cipher.encrypt(bytes(iv)))
#     for x in range(0, len(header) + len(data), 16):
#         for i in range(16):
#             auth[i] = auth[i] ^ buf[x + i]
#         auth = list(cipher.encrypt(bytes(auth)))
#
#     return auth[0:8]
#
#
# class Crypter:
#
#     def __init__(self, key):
#         assert len(key) == 16
#         cipher = AES.new(bytes(key))
#         self._auth_key = cipher.encrypt(bytes(_AUTH_SECRET))
#         self._crypt_key = cipher.encrypt(bytes(_CRYPT_SECRET))
#
#     def Wrap(self, payload, nonce, random, sub_command, src_node, dst_node):
#         assert len(random) == 8
#         assert len(nonce) == 8
#         iv = random + nonce
#         plain = [0] + payload
#         enc = Crypt(self._crypt_key, plain, iv)
#         mac = ComputeMAC(self._auth_key, enc, iv, sub_command, src_node, dst_node)
#         return iv[0:8] + enc + [nonce[0]] + mac
#
#     def Unwrap(self, wrapped, nonce, sub_command, src_node, dst_node):
#         enc_size = len(wrapped) - 8 - 8 - 1
#         iv = wrapped[0:8] + nonce
#         enc = wrapped[8:8 + enc_size]
#         mac_expected = wrapped[-8:]
#         if wrapped[-9] != nonce[0]:
#             logging.error("nonce in wrapped message is off %02x vs %02x",
#                           wrapped[-9], nonce[0])
#             return None
#         mac_actual = ComputeMAC(self._auth_key, enc, iv, sub_command, src_node, dst_node)
#         for a, b in zip(mac_actual, mac_expected):
#             if a != b:
#                 logging.error("mac mismatch %s vs %s", mac_expected, mac_actual)
#                 return None
#         plain = Crypt(self._crypt_key, enc, iv)
#         return plain[1:]
#
#
# class Nonce:
#     def __init(self, value, now):
#         self.value = value
#         self.expiration = now + _NONCE_EXPIRATION_SEC
#
#     def IsExpired(self, now):
#         return now > self.expiration
#
#
# class SecureQueue:
#     """ SecurityQueue handles per node security
#
#     It manages a queue of outbound message that need to encrypted and
#     makes sure that nonces are available to both nodes involved in the communication.
#     An in-bound nonce is provide by *this* node so that the *other* node can send it
#     encrypted messages.
#     An out-bound nonce is provide by the *other* node so that *this* node can send it
#     encrypted messages.
#     """
#
#     def EnqueueMessage(self, message):
#         self._queue.append(message)
#
#     def SetKey(self, key):
#         logging.warning("about to change key to %s", repr(key));
#         self._crypter = _Crypter(key)
#
#     def GetRandomList(self, n):
#         # DEBUGGING HACK FIXME
#         return _CRYPT_SECRET[:n]
#
#     def __init(self, node, controller_node, random):
#         self, _node = node
#         self._controller_node = controller_node
#         self.SetKey(_DEFAULT_KEY)
#         self._queue = []
#
#         # for message send form controller to the node
#         self, _nonce_outbound = Nonce(None, -_NONCE_EXPIRATION_SEC)
#         self, _nonce_outbound_requested = False
#
#     def ProcessReceivedNonce(self, nonce):
#         # we assume the nonce is not expired
#         self._nonce_outbound = nonce
#         if len(self._queue) != 0:
#             return None
#         cmd = self._queue.pop(0)
#         raw = command.AssembleCommand(cmd)
#         wrapped = self._security.Wrap(raw,
#                                       nonce.value,
#                                       self.GetRandomList(8),
#                                       z.Security_MessageEncap,
#                                       self._controller,
#                                       self._node)
#         if cmd[0] == z.Security and cmd[1] == z.Security_NetworkKeySet:
#             self.SetKey(cmd[2])
#
#         return [z.Security, z.Security_MessageEncap, wrapped];
