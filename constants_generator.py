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
constants_generator.py constains code for emitting all Z-Wave related constants
for use with various languages: Python, Dart, HTML (for inspection)

# for constants see:
# https://raw.githubusercontent.com/Z-WavePublic/libzwaveip/master/include/ZW_classcmd.h
"""

import collections
import sys
from typing import Set, Any, Union


def ENUM(base, **subs):
    id_to_str = {}
    for k in subs:
        if base == "":
            fullname = k
        else:
            fullname = base + "_" + k
        globals()[fullname] = subs[k]
        id_to_str[subs[k]] = fullname
    return id_to_str


FIRST_TO_STRING = ENUM(
    "",
    NAK=0x15,
    SOF=0x01,
    ACK=0x06,
    CAN=0x18,
)

SECOND_TO_STRING = ENUM(
    "",
    REQUEST=0,
    RESPONSE=1,
)

NODE_BROADCAST = 0xff

NUM_NODE_BITFIELD_BYTES = 29
MAX_TRIES = 3
MAX_MAX_TRIES = 7
ACK_TIMEOUT = 1000
BYTE_TIMEOUT = 150
RETRY_TIMEOUT = 40000

API_TO_STRING = ENUM(
    "API",
    APPLICATION_COMMAND_HANDLER=0x04,
    APPLICATION_SLAVE_COMMAND_HANDLER=0xA1,
    MEMORY_GET_BYTE=0x21,

    PROMISCUOUS_APPLICATION_COMMAND_HANDLER=0xD1,

    SERIAL_API_APPL_NODE_INFORMATION=0x03,
    SERIAL_API_GET_INIT_DATA=0x02,
    SERIAL_API_GET_CAPABILITIES=0x07,
    SERIAL_API_SET_TIMEOUTS=0x06,
    SERIAL_API_SLAVE_NODE_INFO=0xA0,
    SERIAL_API_SOFT_RESET=0x08,

    ZW_ADD_NODE_TO_NETWORK=0x4a,
    ZW_APPLICATION_UPDATE=0x49,
    ZW_ASSIGN_RETURN_ROUTE=0x46,
    ZW_ASSIGN_SUC_RETURN_ROUTE=0x51,
    ZW_CONTROLLER_CHANGE=0x4d,
    ZW_CREATE_NEW_PRIMARY=0x4c,
    ZW_DELETE_RETURN_ROUTE=0x47,
    ZW_DELETE_SUC_RETURN_ROUTE=0x55,
    ZW_ENABLE_SUC=0x52,

    ZW_GET_CONTROLLER_CAPABILITIES=0x05,
    ZW_GET_NODE_PROTOCOL_INFO=0x41,
    ZW_GET_RANDOM=0x1c,
    ZW_GET_ROUTING_INFO=0x80,
    ZW_GET_SUC_NODE_ID=0x56,
    ZW_GET_VERSION=0x15,
    ZW_GET_VIRTUAL_NODES=0xA5,

    ZW_IS_FAILED_NODE_ID=0x62,
    ZW_IS_VIRTUAL_NODE=0xA6,

    ZW_MEMORY_GET_ID=0x20,
    ZW_NEW_CONTROLLER=0x43,
    ZW_READ_MEMORY=0x23,
    ZW_REMOVE_FAILED_NODE_ID=0x61,
    ZW_REMOVE_NODE_FROM_NETWORK=0x4b,
    ZW_REPLACE_FAILED_NODE=0x63,
    ZW_REPLICATION_COMMAND_COMPLETE=0x44,
    ZW_REPLICATION_SEND_DATA=0x45,

    ZW_REQUEST_NETWORK_UPDATE=0x53,
    ZW_REQUEST_NODE_INFO=0x60,
    ZW_REQUEST_NODE_NEIGHBOR_UPDATE=0x48,
    ZW_REQUEST_NODE_NEIGHBOR_UPDATE_OPTIONS=0x5a,
    ZW_R_F_POWER_LEVEL_SET=0x17,

    ZW_SEND_DATA=0x13,
    ZW_SEND_NODE_INFORMATION=0x12,
    ZW_SEND_SLAVE_DATA=0xA3,
    ZW_SEND_SLAVE_NODE_INFO=0xA2,

    ZW_SET_DEFAULT=0x42,
    ZW_SET_LEARN_MODE=0x50,
    ZW_SET_LEARN_NODE_STATE=0x40,
    ZW_SET_PROMISCUOUS_MODE=0xD0,
    ZW_SET_SLAVE_LEARN_MODE=0xA4,
    ZW_SET_SUC_NODE_ID=0x54,

    ZW_SET_R_F_RECEIVE_MODE=0x10,
    ZW_SEND_DATA_MULTI=0x14,
    ZW_SEND_DATA_ABORT=0x16,
    ZW_SEND_DATA_META=0x18,
    ZW_MEMORY_PUT_BYTE=0x22,
    ZW_MEMORY_PUT_BUFFER=0x24,
    ZW_SEND_SUC_ID=0x57,
    FUNC_ID_LOCK_ROUTE_RESPONSE=0x90,
)
# ======================================================================
TRANSMIT_OPTION_TO_STRING = ENUM(
    "TRANSMIT_OPTION",
    ACK=1,
    LOW_POWER=2,
    AUTO_ROUTE=4,
    NO_ROUTE=16,
    EXPLORE=32,
)

TRANSMIT_COMPLETE_TO_STRING = ENUM(
    "TRANSMIT_COMPLETE",
    OK=0,
    NO_ACK=1,
    FAIL=2,
    NOT_IDLE=3,
    NOROUTE=4,
    HOP_0_FAIL=5,
    HOP_1_FAIL=6,
    HOP_2_FAIL=7,
    HOP_3_FAIL=8,
    HOP_4_FAIL=9,
)


def PrettifyTransmitStatus(b):
    return TRANSMIT_COMPLETE_TO_STRING.get(b, "%02x" % b)


ADD_NODE_TO_STRING = ENUM(
    "ADD_NODE",
    ANY=1,
    CONTROLLER=2,
    SLAVE=3,
    EXISTING=4,
    STOP=5,
    STOP_FAILED=6,
)

ADD_NODE_HIGH_POWER = 0x80

ADD_NODE_STATUS_TO_STRING = ENUM(
    "ADD_NODE_STATUS",
    LEARN_READY=1,
    NODE_FOUND=2,
    ADDING_SLAVE=3,
    ADDING_CONTROLLER=4,
    PROTOCOL_DONE=5,
    DONE=6,
    FAILED=7,
    # not documented - probably a firmware bug in aeon labs dongle
    NOT_INCLUSION_CONTROLLER=35,
)

REMOVE_NODE_TO_STRING = ENUM(
    "REMOVE_NODE",
    ANY=1,
    CONTROLLER=2,
    SLAVE=3,
    STOP=5,
)

REMOVE_NODE_STATUS_TO_STRING = ENUM(
    "REMOVE_NODE_STATUS",
    LEARN_READY=1,
    NODE_FOUND=2,
    REMOVING_SLAVE=3,
    REMOVING_CONTROLLER=4,
    DONE=6,
    FAILED=7,
    NOT_INCLUSION_CONTROLLER=35,
)

LEARN_MODE_STATUS_TO_STRING = ENUM(
    "LEARN_MODE_STATUS",
    STARTED=1,
    DONE=6,
    FAILED=7,
    DELETED=0x80,
)

LEARN_MODE_TO_STRING = ENUM(
    "LEARN_MODE",
    DISABLE=0,
    CLASSIC=1,
    NWI=2,
)

CONTROLLER_CHANGE_TO_STRING = ENUM(
    "CONTROLLER_CHANGE",
    START=2,
    STOP=5,
    STOP_FAILED=6
)

RECEIVE_STATUS_TO_STRING = ENUM(
    "RECEIVE_STATUS",
    ROUTED_BUSY=1,
    ROUTED_LOW_POWER=2,
    TYPE_BROAD=4,
    TYPE_MULTI=8,
)


def PrettifyStatus(b):
    out = []
    for i in RECEIVE_STATUS_TO_STRING:
        if i & b:
            out.append(RECEIVE_STATUS_TO_STRING[i])
            b &= ~i
    if b != 0:
        out.append("%x" % b)
    return "|".join(out)


CREATE_PRIMARY_START = 2
CREATE_PRIMARY_STOP = 5
CREATE_PRIMARY_STOP_FAILED = 6

REQUEST_NEIGHBOR_UPDATE_STARTED = b"\x21"
REQUEST_NEIGHBOR_UPDATE_DONE = b"\x22"
REQUEST_NEIGHBOR_UPDATE_FAILED = b"\x23"


RECEIVE_STATUS_TO_STRING = ENUM(
    "FAILED_NODE",
    OK=0,
    REMOVED=1,
    NOT_REMOVED=2,
    REPLACE_WAITING=3,
    REPLACE_DONE=4,
    REPLACE_FAILED=5,
)

REMOVE_FAILED_NODE_TO_STRING = ENUM(
    "REMODE_FAILED_NODE",
    NOT_PRIMARY_CONTROLLER=2,
    NO_CALLBACK_FUNCTION=4,
    NODE_NOT_FOUND=8,
    NODE_REMOVE_PROCESS_BUSY=16,
    NODE_REMOVE_FAIL=32,
)

SUC_UPDATE_DONE = b"\x00"
SUC_UPDATE_ABORT = b"\x01"
SUC_UPDATE_WAIT = b"\x02"
SUC_UPDATE_DISABLED = b"\x03"
SUC_UPDATE_OVERFLOW = b"\x04"

SUC_FUNC_BASIC_SUC = b"\x00"
SUC_FUNC_NODEID_SERVER = b"\x01"

UPDATE_STATE_TO_STRING = ENUM(
    "UPDATE_STATE",
    NODE_INFO_RECEIVED=0x84,
    NODE_INFO_REQ_DONE=0x82,
    NODE_INFO_REQ_FAILED=0x81,

    ROUTING_PENDING=0x80,
    NEW_ID_ASSIGNED=0x40,
    DELETE_DONE=0x20,
    SUC_ID=0x10
)

APPLICATION_NODEINFO_LISTENING = 1
APPLICATION_NODEINFO_OPTIONAL_FUNCTIONALITY = 2

SLAVE_ASSIGN_COMPLETE = 0
SLAVE_ASSIGN_NODEID_DONE = 1
SLAVE_ASSIGN_RANGE_INFO_UPDATE = 2

SLAVE_LEARN_MODE_DISABLE = 0
SLAVE_LEARN_MODE_ENABLE = 1
SLAVE_LEARN_MODE_ADD = 2
SLAVE_LEARN_MODE_REMOVE = 3

# for ZW_GET_CONTROLLER_CAPABILITIES
CAP_CONTROLLER_TO_STRING = ENUM(
    "CAP_CONTROLLER",
    SECONDARY=1,
    ON_OTHER_NETWORK=2,
    SIS=4,
    REAL_PRIMARY=8,
    SUC=16
)

# for SERIAL_API_GET_INIT_DATA bit-mask
SERIAL_CAP_TO_STRING = ENUM(
    "SERIAL_CAP",
    SLAVE=1,
    TIMER_SUPPORT=2,
    SECONDARY=4,
    SUC=8, )

LIBRARY_TYPE_MAP = [
    "Unknown",
    "Static Controller",
    "Controller",
    "Enhanced Slave",
    "Slave",
    "Installer",
    "Routing Slave",
    "Bridge Controller",
    "Device Under Test"
]

############################################################
#
############################################################

SUBCMD_TO_STRING = {}
CMD_TO_STRING = {}
SUBCMD_TO_PARSE_TABLE = {}

_ALLOWED_PARAMETER_FORMATS = {
    "3{XXX}",  # 24bit
    "A{code}",
    "A{name}",
    "A{commands}",
    "B{alarm}",
    "B{class}",
    "B{control}",
    "B{count}",
    "B{dayhour}",
    "B{delay}",
    "B{duration}",
    "B{endpoint}",
    "B{extra}",
    "B{generic}",
    "B{group}",
    "B{key}",
    "B{keys}",
    "B{level}",
    "B{user}",
    "B{library}",
    "B{min}",
    "B{minute}",
    "B{mode}",
    "B{node}",
    "B{parameter}",
    "B{profiles}",
    "B{protection}",
    "B{role}",
    "B{scale}",
    "B{scene}",
    "B{schemes}",
    "B{sec}",
    "B{seq}",
    "B{specific}",
    "B{state}",
    "B{status}",
    "B{thermo}",
    "B{timeout}",
    "B{type1}",
    "B{type2}",
    "B{type}",
    "B{user}",
    "B{version}",
    "C{date}",
    "G{groups}",
    "F{bytes}",
    "K{key}",
    "L{code}",
    "L{command}",
    "L{data}",
    "L{extensions}",
    "L{key}",
    "L{nodes}",
    "L{nonce}",
    "L{classes}",
    "L{extra}",
    "M{value}",
    "N{name}",
    "O{nonce}",
    "R{bits}",
    "T{bits}",
    "V{value}",
    "W{firmware}",
    "W{checksum}",
    "W{count}",
    "W{dhm}",
    "W{icon}",
    "W{icon2}",
    "W{id}",
    "W{manufacturer}",
    "W{product}",
    "W{protocol}",
    "W{type}",
    "X{value}",
    # optional
    "t{targets}",
    "b{scale}",
    "b{sensor}",
    "b{hardware}",
}


def CheckParseFormat(f):
    if f == "":
        return
    tokens = f.split(",")
    for param in tokens:
        assert param in _ALLOWED_PARAMETER_FORMATS, param


def C(base, cmd, **subs):
    """Register a Command Class"""
    global SUBCMD_TO_STRING
    global CMD_TO_STRING
    global SUBCMD_TO_PARSE_TABLE

    assert cmd not in CMD_TO_STRING, "duplicate command: %s" % cmd
    CMD_TO_STRING[cmd] = base
    # assert base not in globals()
    globals()[base] = cmd

    for k in subs:
        subcmd, parse_format = subs[k]
        CheckParseFormat(parse_format)
        fullname = base + "_" + k
        # assert fullname not in globals
        globals()[fullname] = subcmd
        key = (cmd, subcmd)
        assert key not in SUBCMD_TO_STRING
        SUBCMD_TO_STRING[key] = fullname
        assert key not in SUBCMD_TO_PARSE_TABLE
        table = []
        if parse_format != "":
            table = parse_format.split(",")
        SUBCMD_TO_PARSE_TABLE[key] = table


def CommandToString(c):
    global CMD_TO_STRING
    return CMD_TO_STRING.get(c, "%02x" % c)


def SubCommandToString(c, s):
    global SUBCMD_TO_STRING
    key = (c, s)
    return SUBCMD_TO_STRING.get(key, "%02x" % s)


C("NoOperation", 0x00,
  Set=(0x0, ""))

C("Basic", 0x20,
  Set=(0x1, "B{level}"),
  Get=(0x2, ""),
  Report=(0x3, "B{level}"))

C("ControllerReplication", 0x21,
  TransferGroup=(0x31, "B{seq},B{group},B{node}"),
  # TransferGroupName=(0x32, "B{seq},B{group},S{name}"),  # ERROR use N?
  TransferScene=(0x33, "B{seq},B{scene},B{node},B{level}"),
  # TransferSceneName=(0x34, "B{seq},B{scene},S{name}"),   #ERROR use N?
  )

C("ApplicationStatus", 0x22,
  Busy=(0x01, "B{status},B{delay}"),
  RejectedRequest=(0x02, "B{status}")
  )

C("SwitchBinary", 0x25,
  Set=(0x1, "B{level}"),
  Get=(0x2, ""),
  Report=(0x3, "B{level}"))

C("SwitchMultilevel", 0x26,
  Set=(0x01, "B{level},B{duration}"),
  Get=(0x02, ""),
  Report=(0x03, "B{level}"),
  StartLevelChange=(0x04, "B{mode},L{command}"),
  StopLevelChange=(0x05, ""),
  SupportedGet=(0x06, ""),
  SupportedReport=(0x07, "B{type1},B{type2}"))

C("SwitchAll", 0x27,
  Set=(0x1, "B{mode}"),
  Get=(0x2, ""),
  Report=(0x3, "B{mode}"),
  On=(0x4, ""),
  Off=(0x5, ""))

C("SwitchToggleBinary", 0x28,
  Set=(0x1, ""),
  Get=(0x2, ""),
  Report=(0x3, "B{level}"))

C("SceneActivation", 0x2B,
  Set=(0x1, "B{scene},B{delay}"))

C("SceneActuatorConf", 0x2c,
  Set=(0x1, "B{scene},B{delay},B{extra},B{level}"),
  Get=(0x2, "B{scene}"),
  Report=(0x3, "B{scene},B{level},B{delay}"))

C("SceneControllerConf", 0x2d,
  Set=(0x1, "B{delay},B{group},B{scene}"),
  Get=(0x2, "B{group}"),
  Report=(0x3, "B{delay},B{group},B{scene}"))

C("SensorBinary", 0x30,
  Get=(0x2, ""),
  Report=(0x3, "B{level}"))

C("SensorMultilevel", 0x31,
  SupportedGet=(0x1, "b{sensor}"),
  SupportedReport=(0x2, "R{bits}"),
  Get=(0x4, "b{sensor}"),
  Report=(0x5, "B{type},X{value}"))

C("Meter", 0x32,
  Get=(0x1, "b{scale}"),
  Report=(0x2, "M{value}"),
  SupportedGet=(0x3, ""),
  SupportedReport=(0x4, "B{type},B{scale}"),
  Reset=(0x5, ""))

C("ColorSwitch", 0x33,
  Get=(0x3, "B{group}"),
  Report=(0x4, "B{group},B{level}"),
  SupportedGet=(0x1, ""),
  SupportedReport=(0x2, "R{bits}"),
  # Set=(0x5,
  # StartLevelChange=(0x6,
  # StopLevelChange=(0x7,
  )

C("ThermostatMode", 0x40,
  Set=(0x1, "B{thermo}"),
  Get=(0x2, ""),
  Report=(0x3, "B{thermo}"),
  SupportedGet=(0x4, ""),
  SupportedReport=(0x5, "R{bits}"),
  )

C("ThermostatSetpoint", 0x43,
  # Set=(0x1, ""), # TODO
  Get=(0x2, "B{thermo}"),
  Report=(0x3, "B{thermo},X{value}"),
  SupportedGet=(0x4, ""),
  SupportedReport=(0x5, "R{bits}"),
  )

C("DoorLockLogging", 0x4C,
  SupportedGet=(0x1, ""),  # ok
  SupportedReport=(0x2, "B{count}"),
  Get=(0x3, "B{count}"),
  Report=(0x4, "B{count},C{date},B{type},B{user},A{code}"),
  )

C("ScheduleEntryLock", 0x4e)

C("AssociationGroupInformation", 0x59,
  NameGet=(0x1, "B{group}"),
  NameReport=(0x2, "B{group},A{name}"),
  InfoGet=(0x3, "B{mode},B{group}"),
  InfoReport=(0x4, "B{mode},G{groups}"),
  ListGet=(0x5, "B{mode},B{group}"),
  ListReport=(0x6, "B{group},A{commands}"),
  )

C("ZwavePlusInfo", 0x5e,
  Get=(0x01, ""),
  Report=(0x02, "B{version},B{role},B{type},W{icon},W{icon2}"),
  )

C("MultiChannel", 0x60,
  Get=(0x4, "B{mode}"),
  Report=(0x5, "B{mode},B{count}"),
  Encap=(0x6, "B{mode},L{command}"),
  EndPointGet=(0x07, ""),
  EndPointReport=(0x08, "B{mode},B{count}"),
  CapabilityGet=(0x09, "B{endpoint}"),
  CapabilityReport=(0x0a, "B{endpoint},B{generic},B{specific},L{classes}"),
  ChannelEndPointFind=(0x0b, ""),
  ChannelEndPointFindReport=(0x0c, ""),
  ChannelEncap=(0x0d, ""),
  )

C("DoorLock", 0x62,
  Set=(0x1, "B{status}"),
  Get=(0x2, ""),
  Report=(0x3, "B{status}"),
  ConfigurationSet=(0x4, "B{timeout},B{control},B{min},B{sec}"),
  ConfigurationGet=(0x5, ""),
  ConfigurationReport=(0x6, "B{timeout},B{control},B{min},B{sec}"),
  )

C("UserCode", 0x63,
  Set=(0x1, ""),  # TODO
  Get=(0x2, "B{user}"),
  Report=(0x3, "B{user},B{status},L{code}"),
  NumberGet=(0x4, ""),
  NumberReport=(0x5, "B{count}"),
  )

C("Configuration", 0x70,
  Set=(0x4, "B{parameter},V{value}"),
  Get=(0x5, "B{parameter}"),
  Report=(0x6, "B{parameter},V{value}"),
  )

C("Alarm", 0x71,
  Get=(0x4, ""),
  Report=(0x5, "B{type},B{level}"),
  Set=(0x6, "B{type},B{status}"),
  SupportedGet=(0x7, ""),
  SupportedReport=(0x8, ""),
  )

C("ManufacturerSpecific", 0x72,
  Get=(0x4, ""),
  Report=(0x5, "W{manufacturer},W{type},W{product}"),
  DeviceSpecificGet=(0x6, "B{type}"),
  DeviceSpecificReport=(0x7, "B{type},F{bytes}"),
  )

C("Powerlevel", 0x73,
  Set=(0x1, "B{level},B{timeout}"),
  Get=(0x2, ""),
  Report=(0x3, "B{level},B{timeout}"),
  TestNodeSet=(0x4, "B{node},B{level},W{count}"),
  TestNodeGet=(0x5, ""),
  TestNodeGetReport=(0x6, "B{node},B{status},B{level},W{count}"))

C("Protection", 0x75,
  Set=(0x1, "B{protection}"),
  Get=(0x2, ""),
  Report=(0x3, "B{protection}"))

C("Lock", 0x76,
  Set=(0x1, "B{state}"),
  Get=(0x2, ""),
  Report=(0x3, "B{state}"))

C("NodeNaming", 0x77,
  Set=(0x1, "N{name}"),
  Get=(0x2, ""),
  Report=(0x3, "N{name}"),
  LocationSet=(0x4, "N{name}"),
  LocationGet=(0x5, ""),
  LocationReport=(0x6, "N{name}"))

C("Firmware", 0x7a,
  MetadataGet=(0x1, ""),
  MetadataReport=(0x2, "W{manufacturer},W{id},W{checksum}"),
  )

C("RemoteAssociationActivate", 0x7c)

C("Battery", 0x80,
  Get=(0x2, ""),
  Report=(0x3, "B{level}"))

C("Clock", 0x81,
  Set=(0x4, "B{dayhour},B{minute}"),
  Get=(0x5, ""),
  Report=(0x6, "W{dhm}"),
  )

C("Hail", 0x82,
  Hail=(0x1, ""))

C("WakeUp", 0x84,
  IntervalSet=(0x04, ""),
  IntervalGet=(0x05, ""),
  IntervalReport=(0x06, ""),
  Notification=(0x07, ""),
  NoMoreInformation=(0x08, ""),
  IntervalCapabilitiesGet=(0x09, ""),
  IntervalCapabilitiesReport=(0x0a, "3{XXX},3{XXX},3{XXX},3{XXX}"))

C("Association", 0x85,
  Set=(0x1, "B{group},L{nodes}"),
  Get=(0x2, "B{group}"),
  Report=(0x3, "B{group},B{count},B{seq},L{nodes}"),
  Remove=(0x4, "B{group},L{nodes}"),
  GroupingsGet=(0x5, ""),
  GroupingsReport=(0x6, "B{count}"))

C("Version", 0x86,
  Get=(0x11, ""),
  Report=(0x12, "B{library},W{protocol},W{firmware},b{hardware},t{targets}"),
  CommandClassGet=(0x13, "B{class}"),
  CommandClassReport=(0x14, "B{class},B{version}"))

C("Indicator", 0x87,
  Set=(0x1, "B{status}"),
  Get=(0x2, ""),
  Report=(0x3, "B{status}"))

C("SensorAlarm", 0x9c,
  Get=(0x1, "B{alarm}"),
  Report=(0x2, "B{node},B{alarm}"),
  SupportedGet=(0x3, ""),
  SupportedReport=(0x4, "T{bits}"))

C("SilenceAlarm", 0x9d,
  )

C("Security", 0x98,
  SupportedGet=(0x02, ""),  # ok
  SupportedReport=(0x03, "B{mode},L{command}"),
  SchemeGet=(0x04, "B{mode}"),
  SchemeReport=(0x05, "B{mode}"),
  NetworkKeySet=(0x06, "K{key}"),  # ok
  NetworkKeyVerify=(0x07, ""),  # ok
  SchemeInherit=(0x08, ""),
  NonceGet=(0x40, ""),  # ok TRANSMIT_OPTION_ACK | TRANSMIT_OPTION_AUTO_ROUTE
  NonceReport=(0x80, "O{nonce}"),
  MessageEncap=(0x81, "L{data}"),
  MessageEncapNonceGet=(0xc1, "L{data}"),
  )

C("TimeParameters", 0x8b,
  Set=(0x01, "C{date}"),
  Get=(0x02, ""),
  Report=(0x03, "C{date}"),
  )

C("AssociationCommandConfiguration", 0x9b,
  # NEEDS MORE RESEARCH
  #  SupportedGet=(0x4, ""),  # ok
  #  SupportedReport=(0x5, "B{type},W{count},W{count}"),
  #  Set=(0x1, "B{group},B{node},L{command}"),
  #  Get=(0x2, "B{group},B{node}"),
  #  Report=(0x3, "B{group},B{node},B{type},L{command}"),
  )

C("CentralScene", 0x5b,
  SupportedGet=(0x01, ""),
  SupportedReport=(0x02, "B{count},L{extra}"),
  Notification=(0x03, "B{count},B{mode},B{scene}"),
  )

C("TransportService", 0x55)

C("Supervision", 0x6c)

C("Security2", 0x9f,
  NonceGet=(0x01, "B{seq}"),
  NonceReport=(0x02, "B{seq},B{mode},L{nonce}"),
  MessageEncapsulation=(0x03, "B{seq},B{mode},L{extensions}"),
  KexGet=(0x04, ""),
  KexReport=(0x05, "B{mode},B{schemes},B{profiles},B{keys}"),
  KexSet=(0x06, "B{mode},B{schemes},B{profiles},B{keys}"),
  KexFail=(0x07, "B{type}"),
  PublicKeyReport=(0x08, "B{mode},L{key}"),
  NetworkKeyGet=(0x09, "B{key}"),
  NetworkKeyReport=(0x0a, "B{key},L{key}"),
  NetworkKeyVerify=(0x0b, ""),
  TransferEnd=(0x0c, "B{mode}"),
  CommandsSupportedGet=(0x0d, ""),
  CommandsSupportedReport=(0x0e, "L{classes}"),

  )

C("ManufacturerProprietary", 0x91)
C("SimpleAvControl", 0x94)
C("BasicWindowCovering", 0x50)
C("ClimateControlSchedule", 0x46)
C("CRC16Encap", 0x56)
C("EnergyProduction", 0x90)
C("ScreenMd", 0x92)
C("ScreenAttributes", 0x93)
C("Language", 0x89)
C("MeterPulse", 0x35)
C("MultiCmd", 0x8f)
C("MultiInstanceAssociation", 0x8e)
C("Proprietary", 0x88)
C("SwitchToggleMultilevel", 0x29)
C("ThermostatFanMode", 0x44)
C("ThermostatFanState", 0x45)
C("ThermostatSetBack", 0x47)
C("ThermostatOperatingState", 0x42)

#
C("DeviceResetLocally", 0x5a)

# special
C("Mark", 0xef)

# shut up checker
Mark = 0xef  # will be overwritten by above
############################################################
#
############################################################

BasicDevice = {
    0x1: "Controller",
    0x2: "StaticController",
    0x3: "Slave",
    0x4: "RoutingSlave"
}


def GetBasicDescription(b):
    return BasicDevice.get(b, "0x%02x" % b)


ALLOWED_MAPPED = {
    0x50,  # BasicWindowCovering
    0x62,  # DoorLock
    0x25,  # SwitchBinary
    0x26,  # SwitchMultilevel
    0x28,  # SwitchToggleBinary
    0x29,  # SwitchToggleMultilevel
    0x30,  # SensorBinary
    0x31,  # SensorMultilevel
    0x32,  # Meter
    0x35,  # MeterPulse
    0x40,  # ThermostatMode
    0x43,  # ThermostatSetpoint
    0x46,  # ClimateControlSchedule
    0x71,  # Alarm
    0x94,  # SimpleAvControl
}

ALLOWED_CONTOL: Set[Union[int, Any]] = {
    0x20,  # Basic
    0x21,  # ControllerReplication
    0x60,  # MultiInstance
    0x70,  # Configuration
    0x72,  # ManufacturerSpecific
    0x84,  # WakeUp
    0x85,  # Association
    0x86,  # Version
    0x8e,  # MultiInstanceAssociation
    0x71,  # Alarm
    0x29,  # SwitchToggleMultilevel
    0x25,  # SwitchBinary
    0x2b,  # SceneActivation
    0x26,  # SwitchMultilevel
    0x46,  # ClimateControlSchedule
    0x81,  # Clock
    0x8f,  # MultiCmd
    0x28,  # SwitchToggleBinary
    0x43,  # ThermostatSetpoint
}

GenericSpecificDevice = {
    (0x01, -1): ("Remote Controller", [0xef, 0x20]),
    (0x01, 0x00): ("Remote Controller", []),
    (0x01, 0x01): ("Portable Remote Controller", []),
    (0x01, 0x02): ("Portable Scene Controller", [0x2d, 0x72, 0x85, 0xef, 0x2b]),
    (0x01, 0x03): (
        "Portable Installer Tool", [0x21, 0x72, 0x86, 0x8f, 0xef, 0x21, 0x60, 0x70, 0x72, 0x84, 0x85, 0x86, 0x8e]),
    (0x02, -1): ("Static Controller", [0xef, 0x20]),
    (0x02, 0x01): ("Static PC Controller", []),
    (0x02, 0x02): ("Static Scene Controller", [0x2d, 0x72, 0x85, 0xef, 0x2b]),
    (0x02, 0x03): (
        "Static Installer Tool", [0x21, 0x72, 0x86, 0x8f, 0xef, 0x21, 0x60, 0x70, 0x72, 0x84, 0x85, 0x86, 0x8e]),
    (0x03, -1): ("AV Control Point", [0x20]),
    (0x03, 0x04): ("Satellite Receiver", [0x72, 0x86, 0x94]),
    (0x03, 0x11): ("Satellite Receiver V2", [0x72, 0x86, 0x94], 0x94),
    (0x03, 0x12): ("Doorbell", [0x30, 0x72, 0x85, 0x86], 0x30),
    (0x04, -1): ("Display", [0x20]),
    (0x04, 0x01): ("Simple Display", [0x72, 0x86, 0x92, 0x93]),
    (0x08, -1): ("Thermostat", [0x20]),
    (0x08, 0x01): ("Heating Thermostat", []),
    (0x08, 0x02): ("General Thermostat", [0x40, 0x43, 0x72], 0x40),
    (0x08, 0x03): ("Setback Schedule Thermostat", [0x46, 0x72, 0x86, 0x8f, 0xef, 0x46, 0x81, 0x8f], 0x46),
    (0x08, 0x04): ("Setpoint Thermostat", [0x43, 0x72, 0x86, 0x8f, 0xef, 0x43, 0x8f], 0x43),
    (0x08, 0x05): ("Setback Thermostat", [0x40, 0x43, 0x47, 0x72, 0x86], 0x40),
    (0x08, 0x06): ("General Thermostat V2", [0x40, 0x43, 0x72, 0x86], 0x40),
    (0x09, -1): ("Window Covering", [0x20]),
    (0x09, 0x01): ("Simple Window Covering", [0x50], 0x50),
    (0x0f, -1): ("Repeater Slave", [0x20]),
    (0x0f, 0x01): ("Basic Repeater Slave", []),
    (0x10, -1): ("Binary Switch", [0x20, 0x25], 0x25),
    (0x10, 0x01): ("Binary Power Switch", [0x27]),
    (0x10, 0x03): ("Binary Scene Switch", [0x27, 0x2b, 0x2c, 0x72]),
    (0x11, -1): ("Multilevel Switch", [0x20, 0x26], 0x26),
    (0x11, 0x01): ("Multilevel Power Switch", [0x27]),
    (0x11, 0x03): ("Multiposition Motor", [0x72, 0x86]),
    (0x11, 0x04): ("Multilevel Scene Switch", [0x27, 0x2b, 0x2c, 0x72]),
    (0x11, 0x05): ("Motor Control Class A", [0x25, 0x72, 0x86]),
    (0x11, 0x06): ("Motor Control Class B", [0x25, 0x72, 0x86]),
    (0x11, 0x07): ("Motor Control Class C", [0x25, 0x72, 0x86]),
    (0x12, -1): ("Remote Switch", [0xef, 0x20]),
    (0x12, 0x00): ("Remote Switch", [0xef, 0x20]),
    (0x12, 0x01): ("Binary Remote Switch", [0xef, 0x25], 0x25),
    (0x12, 0x02): ("Multilevel Remote Switch", [0xef, 0x26], 0x26),
    (0x12, 0x03): ("Binary Toggle Remote Switch", [0xef, 0x28], 0x28),
    (0x12, 0x04): ("Multilevel Toggle Remote Switch", [0xef, 0x29], 0x29),
    (0x13, -1): ("Toggle Switch", [0x20]),
    (0x13, 0x01): ("Binary Toggle Switch", [0x25, 0x28], 0x28),
    (0x13, 0x02): ("Multilevel Toggle Switch", [0x26, 0x29], 0x29),
    #    0x14: ("Z/IP Gateway", [0x20]),
    #    (0x14, 0x01): ("Z/IP Tunneling Gateway", [0x23,0x24,0x72,0x86]),
    #    (0x14, 0x02): ("Z/IP Advanced Gateway", [0x23,0x24,0x2f,0x33,0x72,0x86]),
    #    0x15: ("Z/IP Node", []),
    #    (0x15, 0x01): ("Z/IP Tunneling Node", [0x23,0x2e,0x72,0x86]),
    #    (0x15, 0x02): ("Z/IP Advanced Node", [0x23,0x2e,0x2f,0x34,0x72,0x86]),
    #    0x16: ("Ventilation", [0x20]),
    #    (0x16, 0x01): ("Residential Heat Recovery Ventilation", [0x37,0x39,0x72,0x86], 0x39),
    (0x20, -1): ("Binary Sensor", [0x30, 0xef, 0x20], 0x30),
    (0x20, 0x01): ("Routing Binary Sensor", []),
    (0x21, -1): ("Multilevel Sensor", [0x31, 0xef, 0x20], 0x31),
    (0x21, 0x01): ("Routing Multilevel Sensor", []),
    (0x30, -1): ("Pulse Meter", [0x35, 0xef, 0x20], 0x35),
    (0x31, -1): ("Meter", [0xef, 0x20]),
    (0x31, 0x01): ("Simple Meter", [0x32, 0x72, 0x86], 0x32),
    (0x40, -1): ("Entry Control", [0x20]),
    (0x40, 0x01): ("Door Lock", [0x62], 0x62),
    (0x40, 0x02): ("Advanced Door Lock", [0x62, 0x72, 0x86], 0x62),
    (0x40, 0x03): ("Secure Keypad Door Lock", [0x62, 0x63, 0x72, 0x86, 0x98], 0x62),
    (0x50, -1): ("Semi Interoperable", [0x20, 0x72, 0x86, 0x88]),
    (0x50, 0x01): ("Energy Production", [0x90]),
    (0xa1, -1): ("Alarm Sensor", [0xef, 0x20], 0x71),
    (0xa1, 0x00): ("Alarm Sensor", []),
    (0xa1, 0x01): ("Basic Routing Alarm Sensor", [0x71, 0x72, 0x85, 0x86, 0xef, 0x71]),
    (0xa1, 0x02): ("Routing Alarm Sensor", [0x71, 0x72, 0x80, 0x85, 0x86, 0xef, 0x71]),
    (0xa1, 0x03): ("Basic Zensor Alarm Sensor", [0x71, 0x72, 0x86, 0xef, 0x71]),
    (0xa1, 0x04): ("Zensor Alarm Sensor", [0x71, 0x72, 0x80, 0x86, 0xef, 0x71]),
    (0xa1, 0x05): ("Advanced Zensor Alarm Sensor", [0x71, 0x72, 0x80, 0x85, 0x86, 0xef, 0x71]),
    (0xa1, 0x06): ("Basic Routing Smoke Sensor", [0x71, 0x72, 0x85, 0x86, 0xef, 0x71]),
    (0xa1, 0x07): ("Routing Smoke Sensor", [0x71, 0x72, 0x80, 0x85, 0x86, 0xef, 0x71]),
    (0xa1, 0x08): ("Basic Zensor Smoke Sensor", [0x71, 0x72, 0x86, 0xef, 0x71]),
    (0xa1, 0x09): ("Zensor Smoke Sensor", [0x71, 0x72, 0x80, 0x86, 0xef, 0x71]),
    (0xa1, 0x0a): ("Advanced Zensor Smoke Sensor", [0x71, 0x72, 0x80, 0x85, 0x86, 0xef, 0x71]),
    (0xff, -1): ("Non Interoperable", [])
}


def GetGenericSpecificDescription(generic, specific):
    if (generic, specific) in GenericSpecificDevice:
        return GenericSpecificDevice[(generic, specific)][0]
    else:
        return "Unknown: %s" % repr((generic, specific))


def GetGenericSpecificCommands(generic, specific):
    if (generic, specific) in GenericSpecificDevice:
        return GenericSpecificDevice[(generic, specific)][1]
    else:
        return ""


def GetGenericCommands(generic):
    if generic in GenericSpecificDevice:
        return GenericSpecificDevice[generic][1]
    else:
        return ""


############################################################
#
############################################################
FORMAT = collections.namedtuple(
    "FORMAT", ['comment', 'final', 'constint', 'terminator'])

DART_FORMAT = FORMAT(comment="// ", final="final ",
                     constint="const int ", terminator=";")

PYTHON_FORMAT = FORMAT(comment="# ", final="", constint="", terminator="")


def DumpDartConstants(fmt: FORMAT, string_maps=True):
    def DumpDictEntry2(tag, val):
        print("    0x%02x: '%s'," % (tag, val))

    def DumpDictEntry4(tag, val):
        print("    0x%04x: '%s'," % (tag, val))

    def DumpConstAndMap(name, desc):
        print("")
        print(fmt.comment + name)
        vk = sorted([(b, a) for a, b in desc.items()])
        for v, k in vk:
            print("%s%s = 0x%02x%s" % (fmt.constint, v, k, fmt.terminator))
        print("")

        if string_maps:
            print("%s%s_TO_STRING = {" % (fmt.final, name))
            for v, k in vk:
                DumpDictEntry2(k, v)
            print("}" + fmt.terminator)

    def DumpConst(v, k):
        print("%s%s = 0x%02x%s" % (fmt.constint, v, k, fmt.terminator))

    def DumpConstTuple(v, k0, k1):
        print("%s%s = (0x%02x, 0x%02x)%s" % (fmt.constint, v, k0, k1, fmt.terminator))

    print(fmt.comment + "AUTOGENERATED - do not change")
    print(fmt.comment + "Copyright 2016 Robert Muth <robert@muth.org>\n")

    DumpConstAndMap("FIRST", FIRST_TO_STRING)
    DumpConstAndMap("SECOND", SECOND_TO_STRING)
    DumpConstAndMap("API", API_TO_STRING)
    DumpConstAndMap("CAP_CONTROLLER", CAP_CONTROLLER_TO_STRING)
    DumpConstAndMap("SERIAL_CAP", SERIAL_CAP_TO_STRING)
    DumpConstAndMap("UPDATE_STATE", UPDATE_STATE_TO_STRING)
    DumpConstAndMap("TRANSMIT_OPTION", TRANSMIT_OPTION_TO_STRING)
    DumpConstAndMap("TRANSMIT_COMPLETE", TRANSMIT_COMPLETE_TO_STRING)

    DumpConstAndMap("ADD_NODE_STATUS", ADD_NODE_STATUS_TO_STRING)
    DumpConstAndMap("ADD_NODE", ADD_NODE_TO_STRING)

    DumpConstAndMap("REMOVE_NODE_STATUS", REMOVE_NODE_STATUS_TO_STRING)
    DumpConstAndMap("REMOVE_NODE", REMOVE_NODE_TO_STRING)

    DumpConstAndMap("LEARN_MODE", LEARN_MODE_TO_STRING)
    DumpConstAndMap("LEARN_MODE_STATUS", LEARN_MODE_STATUS_TO_STRING)

    DumpConstAndMap("CONTROLLER_CHANGE", CONTROLLER_CHANGE_TO_STRING)

    DumpConstAndMap("REMOVE_FAILED_NODE", REMOVE_FAILED_NODE_TO_STRING)

    if string_maps:
        print("")
        print(fmt.comment + "Commands")
        for k, v in sorted(CMD_TO_STRING.items()):
            DumpConst(v, k)

        print("")
        print(fmt.final + "CMD_TO_STRING = {")
        for k, v in sorted(CMD_TO_STRING.items()):
            DumpDictEntry2(k, v)
        print("}" + fmt.terminator)

        print("")
        print(fmt.comment + "SubCommands")
        for k, v in sorted(SUBCMD_TO_STRING.items()):
            DumpConstTuple(v, k[0], k[1])

        print("")
        print(fmt.final + "SUBCMD_TO_STRING = {")
        for k, v in sorted(SUBCMD_TO_STRING.items()):
            DumpDictEntry4(k[0] * 256 + k[1], v)
        print("}" + fmt.terminator)

    print("")
    print(fmt.final + "GENERIC_SPECIFIC_DB = {")
    for k in sorted(GenericSpecificDevice.keys()):
        v = GenericSpecificDevice[k]
        assert len(k) == 2
        if k[1] == -1:
            continue
        o = GenericSpecificDevice[k[0], -1]
        if len(o) == 3:
            mapped = o[2]
            assert len(v) == 2
        elif len(v) == 3:
            mapped = v[2]
        else:
            mapped = 0

        cmd = []
        cntrl = []
        seen_mark = False
        for i in v[1]:
            if i == Mark:
                seen_mark = True
            elif seen_mark:
                cntrl.append(i)
            else:
                cmd.append(i)
        seen_mark = False
        for i in o[1]:
            if i == Mark:
                seen_mark = True
            elif seen_mark:
                cntrl.append(i)
            else:
                cmd.append(i)

        for i in cmd:
            if i not in CMD_TO_STRING:
                print("missing %x" % i)
                assert False

        for i in cntrl:
            if i not in CMD_TO_STRING:
                print("missing %x" % i)
                assert False

            if i not in ALLOWED_CONTOL:
                print("%x %s" % (i, CMD_TO_STRING.get(i)))
                assert False

        if mapped != 0:
            if mapped not in ALLOWED_MAPPED:
                print("%x %s" % (mapped, CMD_TO_STRING.get(mapped)))
                assert False
        print("    0x%04x : ['%s', %s, %s, 0x%02x]," %
              (k[0] * 256 + k[1], v[0], cmd, cntrl, mapped))
    print("}" + fmt.terminator)

    print("")
    print(fmt.final + "SUBCMD_TO_PARSE_TABLE = {")
    last = None
    for k, v in sorted(SUBCMD_TO_PARSE_TABLE.items()):
        if k[0] != last:
            last = k[0]
            print("")
            print("    " + fmt.comment +
                  CMD_TO_STRING[last] + " (0x%02x = %d)" % (last, last))
        subcmd = SUBCMD_TO_STRING.get((k[0], k[1]), "").split("_")[-1]
        key = k[0] * 256 + k[1]
        s = "    0x%04x: %s," % (key, v)
        print("%s  %s%s (%d)" % (s, fmt.comment, subcmd, k[1]))
    print("}" + fmt.terminator)

    seen = set()
    for v in SUBCMD_TO_PARSE_TABLE.values():
        for x in v:
            seen.add(x)
    if seen != _ALLOWED_PARAMETER_FORMATS:
        assert False, seen.symmetric_difference(_ALLOWED_PARAMETER_FORMATS)


def DumpPythonConstants():
    pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'python':
        DumpDartConstants(PYTHON_FORMAT)
    elif len(sys.argv) > 1 and sys.argv[1] == 'html':
        print("<html><body><pre>")
        DumpDartConstants(PYTHON_FORMAT, False)
        print("</pre></body></html>")
    else:
        DumpDartConstants(DART_FORMAT)
