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
command.py contain code for parsing and assembling API_APPLICATION_COMMAND_requests.

It also contains some logic pertaining to the node state machine.
"""

import logging
import re

from pyzwaver import zwave

UNIT_LEVEL = "level"
UNIT_NONE = ""

# sensor kinds
SENSOR_KIND_SWITCH_BINARY = "SwitchBinary"
SENSOR_KIND_SWITCH_MULTILEVEL = "SwitchMultilevel"
SENSOR_KIND_SWITCH_TOGGLE = "SwitchToggle"
SENSOR_KIND_BATTERY = "Battery"
SENSOR_KIND_BASIC = "Basic"
SENSOR_KIND_RELATIVE_HUMIDITY = "Relative Humidity"
SENSOR_KIND_INVALID = "@invalid@"
SENSOR_KIND_ELECTRIC = "Electric"
SENSOR_KIND_GAS = "Gas"
SENSOR_KIND_WATER = "Water"
SENSOR_KIND_TEMPERTATURE = "Temperature"

#
SECURITY_SET_CLASS = "SecuritySetClass"
SECURITY_SCHEME = "SecurityScheme"
SECURITY_NONCE_RECEIVED = "SecurityNonceReceived"
SECURITY_NONCE_REQUESTED = "SecurityNonceRequested"
SECURITY_UNWRAP = "SecurityUnwrap"
SECURITY_KEY_VERIFY = "SecurityKeyVerify"

EVENT_ALARM = "Alarm"
EVENT_WAKE_UP = "WakeUp"
EVENT_HAIL = "Hail"
EVENT_STATE_CHANGE = "StateChange"
EVENT_NODE_INFO = "NodeInfo"
EVENT_VALUE_CHANGE = "ValueChange"

NODE_STATE_NONE = "0_None"
NODE_STATE_INCLUDED = "1_Included"
# discovered means we have the command classes
NODE_STATE_DISCOVERED = "2_Discovered"
# interviewed means we have received product info (including most static
# info an versions)
NODE_STATE_INTERVIEWED = "3_Interviewed"

_VALUE_NAME_REWRITES = [
    # note: order is important
    ("_Report$", ""),
    ("Report$", ""),
]


def GetValueName(k):
    name = zwave.SUBCMD_TO_STRING[k[0] * 256 + k[1]]
    for a, b in _VALUE_NAME_REWRITES:
        name = re.sub(a, b, name)
    return name


# ======================================================================
METER_TYPES = [
    [SENSOR_KIND_INVALID, [None, None, None, None, None, None, None, None]],
    [SENSOR_KIND_ELECTRIC, ["kWh", "kVAh", "W", "Pulses",
                            "V", "A", "Power-Factor", None]],
    [SENSOR_KIND_GAS, ["m^3", "ft^3", None, "Pulses", None, None, None, None]],
    [SENSOR_KIND_WATER, ["m^3", "ft^3", None, "Pulses", None, None, None, None]],
]

# TODO: introduce constants for units
SENSOR_TYPES = [
    [SENSOR_KIND_INVALID, [None, None, None, None]],
    [SENSOR_KIND_TEMPERTATURE, ["C", "F", None, None]],
    ["General", ["%", None, None, None]],
    ["Luminance", ["%", "lux", None, None]],
    # 4
    ["Power", ["W", "BTU/h", None, None]],
    [SENSOR_KIND_RELATIVE_HUMIDITY, ["%", None, None, None]],
    ["Velocity", ["m/s", "mph", None, None]],
    ["Direction", ["", "", None, None]],
    # 8
    ["Atmospheric Pressure", ["kPa", "inHg", None, None]],
    ["Barometric Pressure", ["kPa", "inHg", None, None]],
    ["Solar Radiation", ["W/m2", None, None, None]],
    ["Dew Point", ["C", "F", None, None]],
    # 12
    ["Rain Rate", ["mm/h", "in/h", None, None]],
    ["Tide Level", ["m", "ft", None, None]],
    ["Weight", ["kg", "lb", None, None]],
    ["Voltage", ["kg", "lb", None, None]],
    # 16
    ["Current", ["A", "mA", None, None]],
    ["CO2 Level", ["ppm", None, None, None]],
    ["Air Flow", ["m3/h", "cfm", None, None]],
    ["Tank Capacity", ["l", "cbm", "gal", None]],
    # 20
    ["Distance", ["m", "cm", "ft", None]],
    ["Angle Position", ["%", "deg N", "deg S", None]],
    ["Rotation", ["rpm", "Hz", None, None]],
    ["Water Temperature", ["C", "F", None, None]],
    # 24
    ["Soil Temperature", ["C", "F", None, None]],
    ["Seismic Intensity",
     ["mercalli", "EU macroseismic", "liedu", "shindo"]],
    ["Seismic Magnitude",
     ["local", "moment", "surface wave", "body wave"]],
    ["Utraviolet", ["", "", None, None]],
    # 28
    ["Electrical Resistivity", ["ohm", None, None, None]],
    ["Electrical Conductivity", ["siemens/m", None, None, None]],
    ["Loudness", ["db", "dbA", None, None]],
    ["Moisture", ["%", "content", "k ohms", "water activity"]],
]

ALARM_TYPE = [
    ["General"],
    ["Smoke"],
    ["Carbon Monoxide"],
    ["Carbon Dioxide"],
    ["Heat"],
    ["Flood"],
]

# second parameter: supports setpoint
TEMPERATURE_MODES = [
    ["Off", False],
    ["Heating", True],
    ["Cooling", True],
    ["Auto", False],
    ["Auxiliary Heat", False],
    ["Resume", False],
    ["Fan Only", False],
    ["Furnace", True],
    ["Dry Air", True],
    ["Moist Air", True],
    ["Auto Changeover", True],
    ["Heating Econ", True],
    ["Cooling Econ", True],
    ["Away Heating", True],
]

DOOR_LOG_EVENT_TYPE = [
    "Lock: Access Code",
    "Unlock: Access Code",
    "Lock: Lock Button",
    "Unlock: Lock Botton",
    "Lock Attempt: Out of Schedule Access Code",
    "Unlock Attempt: Out of Schedule Access Code",
    "Illegal Access Code Entered",
    "Lock: Manual",
    "Unlock: Manual",
    "Lock: Auto",
    "Unlock: Auto",
    "Lock: Remote Out of Schedule Access Code",
    "Unlock: Remote Out of Schedule Access Code",
    "Lock: Remote",
    "Unlock: Remote",
    "Lock Attempt: Remote Out of Schedule Access Code",
    "Unlock Attempt Remote Out of Schedule Access Code",
    "Illegal Remote Access Code",
    "Lock: Manual (2)",
    "Unlock: Manual (2)",
    "Lock Secured",
    "Lock Unsecured",
    "User Code Added",
    "User Code Deleted",
    "All User Codes Deleted",
    "Master Code Changed",
    "User Code Changed",
    "Lock Reset",
    "Configuration Changed",
    "Low Battery",
    "New Battery Installed",
]


def EventTypeToString(t):
    if t < len(DOOR_LOG_EVENT_TYPE):
        return DOOR_LOG_EVENT_TYPE[t]
    return "@UNKNOWN_EVENT[%d]@" % t


# ======================================================================
def _GetSignedValue(m, index, size):
    value = 0
    negative = (m[index] & 0x80) != 0
    for i in range(size):
        value <<= 8
        if negative:
            value += ~m[index + i]
        else:
            value += m[index + i]

    if negative:
        value += 1
        return - float(value)
    else:
        return float(value)


# ======================================================================
def _GetReading(m, index, units_extra):
    size = m[index] & 0x7
    units = (m[index] & 0x18) >> 3 | units_extra
    precision = (m[index] & 0xe0) >> 5
    value = _GetSignedValue(m, index + 1, size) / pow(10, precision)
    return index + 1 + size, [units, value]


def _GetTimeDelta(m, index):
    return index + 2, m[index] * 256 + m[index + 1]


def _ExtractValues(m, index, units_extra):
    # unit = None
    val1 = None
    dt = None
    val2 = None
    if index >= len(m):
        return index, [val1, dt, val2]

    index, (unit, val1) = _GetReading(m, index, units_extra)
    if index + 1 < len(m):
        index, dt = _GetTimeDelta(m, index)
    if index < len(m):
        index, (_, val2) = _GetReading(m, index, units_extra)

    return index, [unit, val1, dt, val2]


def _ParseMeter(m, index):
    # extra = m[index] & 0x60
    units_extra = (m[index] & 0x80) >> 5
    meter_type = m[index] & 0x1f
    index, val = _ExtractValues(m, index + 1, units_extra)
    return index, [meter_type] + val


# ======================================================================
# all parsers return the amount of consumed bytes or a negative number to indicate
# success


def _ParseByte(m, index):
    if len(m) <= index:
        return index, None
    return index + 1, m[index]


def _ParseWord(m, index):
    if len(m) <= index + 1:
        return index, None
    return index + 2, m[index] * 256 + m[index + 1]


_ENCODING_TO_DECODER = [
    "ascii",
    "latin1",  # "cp437" ,
    "utf-16-be",
]


def _ParseName(m, index):
    assert len(m) > index
    encoding = m[index] & 3
    b = bytes(m[index + 1:])
    # TODO(me)
    return len(m), b.decode(_ENCODING_TO_DECODER[encoding])


def _ParseStringWithLength(m, index):
    size = m[index]
    return 1 + size + index, bytes(m[index + 1: size])


def _ParseStringWithLengthAndEncoding(m, index):
    encoding = m[index] >> 5
    size = m[index] & 0x1f
    return 1 + size, [encoding, bytes(m[index + 1:index + size])]


def _ParseListRest(m, index):
    size = len(m) - index
    return index + size, m[index:index + size]


def _ExtractBitVector(data, offset):
    bits = set()
    for i in range(len(data)):
        b = data[i]
        for j in range(8):
            if b & (1 << j) != 0:
                bits.add(j + i * 8 + offset)
    return bits


def _ParseGroups(m, index):
    misc = m[index]
    count = misc & 0x3f
    if len(m) < index + 1 + count * 7:
        logging.error("malformed groups section: %d (%d)", len(m), count)
        return index, None
    groups = []
    index += 1
    for i in range(count):
        num = m[index + 0]
        profile = m[index + 2] * 256 + m[index + 3]
        event = m[index + 5] * 256 + m[index + 6]
        groups.append((num, profile, event))
        index += 7
    return index, groups,


def _ParseBitVector(m, index):
    size = m[index]
    return index + 1 + size, _ExtractBitVector(m[index + 1:index + 1 + size], 0)


def _ParseBitVectorRest(m, index):
    # size = len(m) - index
    return len(m), _ExtractBitVector(m[index:], 0)


def _ParseNonce(m, index):
    size = 8
    if len(m) < index + size:
        logging.error("malformed nonce:")
        return index, None
    return index + size, m[index:index + size]


def _ParseDataRest(m, index):
    size = len(m) - index
    return index + size, m[index:index + size]


def _GetIntLittleEndian(m):
    x = 0
    shift = 0
    for i in m:
        x += i << shift
        shift += 8
    return x


def _GetIntBigEndian(m):
    x = 0
    for i in m:
        x <<= 8
        x += i
    return x


def _ParseRestLittleEndianInt(m, index):
    size = len(m) - index
    return index + size, _GetIntLittleEndian(m[index:index + size])


def _ParseSensor(m, index):
    # we need at least two bytes
    if len(m) < index + 2:
        logging.error("malformed sensor string")
        return index, None

    c = m[index]
    precision = (c >> 5) & 7
    scale = (c >> 3) & 3
    size = c & 7
    if len(m) < index + 1 + size:
        logging.error(
            "malformed sensor string %d %d %d", precision, scale, size)
        return index, None
    value = _GetSignedValue(m, index + 1, size) / pow(10, precision)
    return index + 1 + size, [scale, value]


def _ParseValue(m, index):
    size = m[index] & 0x7
    start = index + 1
    return index + 1 + size, [size, _GetIntBigEndian(m[start:start + size])]


def _ParseDate(m, index):
    if len(m) < index + 7:
        logging.error("malformed time data")
        return len(m), None

    year = m[index] * 256 + m[index + 1]
    month = m[index + 2]
    day = m[index + 3]
    hours = m[index + 4]
    mins = m[index + 5]
    secs = m[index + 6]
    return index + 7, [year, month, day, hours, mins, secs]


_PARSE_ACTIONS = {
    'A': _ParseStringWithLength,
    'F': _ParseStringWithLengthAndEncoding,
    'B': _ParseByte,
    'C': _ParseDate,
    'G': _ParseGroups,
    'N': _ParseName,
    'L': _ParseListRest,
    'R': _ParseRestLittleEndianInt,  # as integer
    "W": _ParseWord,
    "V": _ParseValue,
    "M": _ParseMeter,
    "O": _ParseNonce,
    "D": _ParseDataRest,  # as Uint8List
    "T": _ParseBitVector,
    "U": _ParseBitVectorRest,
    "X": _ParseSensor,
}


def _GetParameterDescriptors(m):
    if len(m) < 2:
        logging.error("malformed command %s", m)
        return None
    key = m[0] * 256 + m[1]
    return zwave.SUBCMD_TO_PARSE_TABLE[key]


def ParseCommand(m, prefix):
    """ParseCommand decodes an API_APPLICATION_COMMAND request into a list of values"""
    table = _GetParameterDescriptors(m)

    if table is None:
        logging.error("%s unknown command", prefix)
        return []

    out = []
    index = 2
    for t in table:
        new_index, value = _PARSE_ACTIONS[t[0]](m, index)
        if value is None:
            logging.error("%s malformed message while parsing format %s %s", prefix, t[0], table)
            return None
        out.append(value)
        index = new_index
    return out


# ======================================================================


def _MakeValue(conf, value):
    size = conf & 7
    assert size in (1, 2, 4)

    data = [conf]
    shift = (size - 1) * 8
    while shift >= 0:
        data.append(0xff & (value >> shift))
        shift -= 8
    return data


def _MakeDate(date):
    return [date[0] // 256, date[0] % 256, date[1], date[2], date[3], date[4], date[5]]


# raw_cmd: [class, subcommand, arg1, arg2, ....]
def AssembleCommand(raw_cmd):
    table = zwave.SUBCMD_TO_PARSE_TABLE[raw_cmd[0] * 256 + raw_cmd[1]]
    assert table is not None
    data = [
        raw_cmd[0],
        raw_cmd[1]
    ]
    # logging.debug("${raw_cmd[0]} ${raw_cmd[1]}: table length:
    # ${table.length}")
    for i in range(len(table)):
        t = table[i]
        v = raw_cmd[i + 2]
        if t[0] == 'B':
            data.append(v)
        elif t[0] == 'Y':
            if v is not None:
                data.append(v)
        elif t[0] == 'N':
            data.append(1)
            # for c in v:
            # out.append(ord(c))
        elif t[0] == 'K':
            if len(v) != 16:
                logging.error("bad key parameter: ${v}")
                assert False
            data += v
        elif t[0] == 'D':
            data += v
        elif t[0] == 'S':
            logging.info("unknown parameter: ${t[0]}")
            assert False, "unreachable"
            # for c in v:
            # out.append(ord(c))
        elif t[0] == 'L':
            data += v
        elif t[0] == 'C':
            data += _MakeDate(v)
        elif t[0] == 'O':
            if len(v) != 8:
                logging.error("bad nonce parameter: ${v}")
            data += v
        elif t[0] == 'V':
            data += _MakeValue(v[0], v[1])
        else:
            logging.error("unknown parameter: ${t[0]}")
            assert False, "unreachable"

    return data


# ======================================================================
class Value:
    def __init__(self, kind, unit, value, meter_time_delta=0, meter_prev=0.0):
        self.kind = kind
        self.unit = unit
        self.value = value
        self.meter_prev = meter_prev
        self.meter_time_delta = meter_time_delta

    def __lt__(self, other):
        if self.kind != other.kind:
            return self.kind < other.kind
        if self.unit != other.unit:
            return self.unit < other.unit
        return False

    def __str__(self):
        if self.unit == UNIT_NONE:
            return "%s[%s]" % (self.value, self.kind)
        else:
            return "%s[%s, %s]" % (self.value, self.kind, self.unit)


def ValueSensorNormal(value, prefix):
    kind = value[0]
    info = SENSOR_TYPES[kind]
    assert len(value[1]) == 2
    scale, reading = value[1]
    unit = info[1][scale]
    if unit is None:
        logging.error("%s bad sensor reading [%d, %d]: %s",
                      prefix, kind, scale, info)
    assert unit is not None
    return Value(info[0], unit, reading)


def ValueMeterNormal(value, prefix):
    val = value[0]
    if len(val) != 5:
        logging.error("%s bad meter normal %s",
                      prefix, value)
        return None
    kind = val[0]
    scale = val[1]
    info = METER_TYPES[kind]
    unit = info[1][scale]
    assert unit is not None
    return Value(info[0], unit, val[2], val[3], val[4])


def ValueBare(k, value):
    return Value(GetValueName(k), UNIT_NONE, value)


# ======================================================================
_STORE_VALUE_SCALAR_ACTIONS = [
    (zwave.SwitchAll, zwave.SwitchAll_Report),
    (zwave.ColorSwitch, zwave.ColorSwitch_SupportedReport),
    (zwave.Protection, zwave.Protection_Report),
    (zwave.NodeNaming, zwave.NodeNaming_Report),
    (zwave.NodeNaming, zwave.NodeNaming_LocationReport),
    (zwave.TimeParameters, zwave.TimeParameters_Report),
    (zwave.Lock, zwave.Lock_Report),
    (zwave.Indicator, zwave.Indicator_Report),
    (zwave.SwitchMultilevel, zwave.SwitchMultilevel_StopLevelChange),
    (zwave.WakeUp, zwave.WakeUp_IntervalCapabilitiesReport),
    (zwave.SwitchMultilevel, zwave.SwitchMultilevel_SupportedReport),
    (zwave.DoorLock, zwave.DoorLock_Report),
    (zwave.DoorLockLogging, zwave.DoorLockLogging_SupportedReport),
    (zwave.UserCode, zwave.UserCode_NumberReport),
    # set - a few requests may actually be sent to the controller
    (zwave.Basic, zwave.Basic_Set),
    (zwave.SceneActivation, zwave.SceneActivation_Set),
    (zwave.Clock, zwave.Clock_Report),
]

_STORE_VALUE_LIST_ACTIONS = [
    (zwave.Alarm, zwave.Alarm_SupportedReport),
    (zwave.Powerlevel, zwave.Powerlevel_Report),
    (zwave.SensorAlarm, zwave.SensorAlarm_SupportedReport),
    (zwave.ThermostatMode, zwave.ThermostatMode_Report),
    # needs work
    (zwave.ManufacturerSpecific, zwave.ManufacturerSpecific_DeviceSpecificReport),
    (zwave.ApplicationStatus, zwave.ApplicationStatus_Busy),
    (zwave.MultiInstance, zwave.MultiInstance_ChannelEndPointReport),
    (zwave.SwitchMultilevel, zwave.SwitchMultilevel_StartLevelChange),
    (zwave.DoorLock, zwave.DoorLock_ConfigurationReport),
    (zwave.ZwavePlusInfo, zwave.ZwavePlusInfo_Report),
    (zwave.Version, zwave.Version_Report),
    (zwave.ManufacturerSpecific, zwave.ManufacturerSpecific_Report),
    (zwave.Firmware, zwave.Firmware_MetadataReport),
]

# ======================================================================
# This is the main dispatch table for incoming "commands", e.g. reports
# ======================================================================
ACTIONS = {
    (zwave.SceneActuatorConf, zwave.SceneActuatorConf_Report):
        (lambda n, v, k, p: None, -1, EVENT_VALUE_CHANGE),
    #
    # COMMAND
    #
    (zwave.Version, zwave.Version_CommandClassReport):
        (lambda n, v, k, p: n.commands.SetVersion(v), 2, EVENT_VALUE_CHANGE),
    #
    # SENSOR
    #
    (zwave.SensorMultilevel, zwave.SensorMultilevel_Report):
        (lambda n, v, k, p: n.sensors.Set(ValueSensorNormal(v, p)), 2, EVENT_VALUE_CHANGE),
    (zwave.SensorMultilevel, zwave.SensorMultilevel_SupportedReport):
        (lambda n, v, k, p: n.sensors.SetSupported(v), 1, EVENT_VALUE_CHANGE),
    (zwave.SwitchBinary, zwave.SwitchBinary_Report):
        (lambda n, v, k, p: n.sensors.Set(
            Value(SENSOR_KIND_SWITCH_BINARY, UNIT_LEVEL, v[0])), 1, EVENT_VALUE_CHANGE),
    (zwave.Battery, zwave.Battery_Report):
        (lambda n, v, k, p: n.sensors.Set(
            Value(SENSOR_KIND_BATTERY, UNIT_LEVEL, v[0])), 1, EVENT_VALUE_CHANGE),
    (zwave.SensorBinary, zwave.SensorBinary_Report):
        (lambda n, v, k, p: n.sensors.Set(
            Value(SENSOR_KIND_SWITCH_BINARY, UNIT_LEVEL, v[0])), 1, EVENT_VALUE_CHANGE),
    (zwave.SwitchToggleBinary, zwave.SwitchToggleBinary_Report):
        (lambda n, v, k, p: n.sensors.Set(
            Value(SENSOR_KIND_SWITCH_TOGGLE, UNIT_LEVEL, v[0])), 1, EVENT_VALUE_CHANGE),
    (zwave.SwitchMultilevel, zwave.SwitchMultilevel_Report):
        (lambda n, v, k, p: n.sensors.Set(
            Value(SENSOR_KIND_SWITCH_MULTILEVEL, UNIT_LEVEL, v[0])), 1, EVENT_VALUE_CHANGE),
    (zwave.Basic, zwave.Basic_Report):
        (lambda n, v, k, p: n.sensors.Set(
            Value(SENSOR_KIND_BASIC, UNIT_LEVEL, v[0])), 1, EVENT_VALUE_CHANGE),
    #
    # METER
    #
    (zwave.Meter, zwave.Meter_Report):
        (lambda n, v, k, p: n.meters.Set(ValueMeterNormal(v, p)), 1, EVENT_VALUE_CHANGE),
    (zwave.Meter, zwave.Meter_SupportedReport):
        (lambda n, v, k, p: n.meters.SetSupported(v), 2, EVENT_VALUE_CHANGE),
    #
    # PARAMETER
    #
    (zwave.Configuration, zwave.Configuration_Report):
        (lambda n, v, k, p: n.parameters.Set(v), 2, EVENT_VALUE_CHANGE),
    #
    # ASSOCIATIONS
    #
    (zwave.Association, zwave.Association_GroupingsReport):
        (lambda n, v, k, p: n.associations.StoreCount(v), 1, EVENT_VALUE_CHANGE),
    (zwave.Association, zwave.Association_Report):
        (lambda n, v, k, p: n.associations.StoreNodes(v), 4, EVENT_VALUE_CHANGE),
    (zwave.AssociationGroupInformation, zwave.AssociationGroupInformation_NameReport):
        (lambda n, v, k, p: n.associations.StoreName(v), 2, EVENT_VALUE_CHANGE),
    (zwave.AssociationGroupInformation, zwave.AssociationGroupInformation_InfoReport):
        (lambda n, v, k, p: n.associations.StoreMeta(v), -1, EVENT_VALUE_CHANGE),
    (zwave.AssociationGroupInformation, zwave.AssociationGroupInformation_ListReport):
        (lambda n, v, k, p: n.associations.StoreCommands(v), 2, EVENT_VALUE_CHANGE),
    #
    # MAP VALUES
    (zwave.ColorSwitch, zwave.ColorSwitch_Report):
        (lambda n, v, k, p: n.values.SetMap(k, ValueBare(k, {v[0]: v[1]})),
         2, EVENT_VALUE_CHANGE),

    #
    #
    # EVENTS
    #
    (zwave.Alarm, zwave.Alarm_Report):
        (lambda n, v, k, p: n.StoreEvent(
            Value(EVENT_ALARM, UNIT_NONE, v)), -1, None),
    (zwave.Alarm, zwave.Alarm_Set):
        (lambda n, v, k, p: n.StoreEvent(
            Value(EVENT_ALARM, UNIT_NONE, v)), -1, None),
    (zwave.WakeUp, zwave.WakeUp_Notification):
        (lambda n, v, k, p: n.StoreEvent(Value(EVENT_WAKE_UP, UNIT_NONE, 1)),
         -1, None),
    #
    # These need a lot more work
    #
    (zwave.Security, zwave.Security_SchemeReport): [SECURITY_SCHEME],
    (zwave.Security, zwave.Security_NonceReport): [SECURITY_NONCE_RECEIVED],
    (zwave.Security, zwave.Security_NonceGet): [SECURITY_NONCE_REQUESTED],
    (zwave.Security, zwave.Security_SupportedReport): [SECURITY_SET_CLASS],
    (zwave.Security, zwave.Security_MessageEncap): [SECURITY_UNWRAP],
    (zwave.Security, zwave.Security_NetworkKeyVerify): [SECURITY_KEY_VERIFY],

    # maps incoming API_APPLICATION_COMMAND messages to action we want to take
    # Most of the time we deal with "reports" and the action will be to
    # store some value inside the message for later use.
    # NODE_ACTION_TO_BE_REVISITED = {
    #     #
    #     (zwave.MultiInstance, zwave.MultiInstance_Report):
    #     [ACTION_STORE_MAP, VALUE_TYPE_MAP_SCALAR, "multi_instance"],
    #     (zwave.SceneControllerConf, zwave.SceneControllerConf_Report):
    #     [ACTION_STORE_MAP, VALUE_TYPE_MAP_LIST, "button"],
    #     (zwave.ApplicationStatus, zwave.ApplicationStatus_RejectedRequest):
    #     [ACTION_STORE_EVENT, VALUE_TYPE_CONST, "rejected_request", 1],
    #     #
    #     (zwave.Basic, zwave.Basic_Get):
    #     [ACTION_STORE_EVENT, VALUE_TYPE_CONST, "BASIC_GET", 1],
    #     #
    #     (zwave.UserCode, zwave.UserCode_Report):
    #     [ACTION_STORE_MAP, VALUE_TYPE_MAP_LIST, "user_code"],
    #     (zwave.DoorLockLogging, zwave.DoorLockLogging_Report):
    #     [ACTION_STORE_MAP, VALUE_TYPE_MAP_LIST, "lock_log"],
    #     #
    #     (zwave.Hail, zwave.Hail_Hail):
    #     [ACTION_STORE_EVENT, VALUE_TYPE_CONST, "HAIL", 1],
    #     # ZWAVE+
    #     # SECURITY
    #     #
}

STATE_CHANGE = {
    (zwave.ManufacturerSpecific, zwave.ManufacturerSpecific_Report):
        (lambda n, v, k, p: n._MaybeChangeState(NODE_STATE_INTERVIEWED), -1, None),
}


def PatchUpActions():
    global ACTIONS
    logging.info("PatchUpActions")
    for key in _STORE_VALUE_SCALAR_ACTIONS:
        ACTIONS[key] = (lambda n, v, k, p: n.values.Set(k, ValueBare(k, v[0])),
                        1, EVENT_VALUE_CHANGE)

    for key in _STORE_VALUE_LIST_ACTIONS:
        ACTIONS[key] = (lambda n, v, k, p: n.values.Set(k, ValueBare(k, v)),
                        -1, EVENT_VALUE_CHANGE)


PatchUpActions()


def RenderSensorList(values):
    return str([SENSOR_TYPES[x][0] for x in values])


def RenderMeterList(meter, values):
    return str([METER_TYPES[meter][1][x] for x in values])
