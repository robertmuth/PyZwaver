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

from pyzwaver import zwave as z

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
    name = z.SUBCMD_TO_STRING[k[0] * 256 + k[1]]
    for a, b in _VALUE_NAME_REWRITES:
        name = re.sub(a, b, name)
    return name


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

# ======================================================================
_STORE_VALUE_SCALAR_ACTIONS = [
    (z.SwitchAll, z.SwitchAll_Report),
    (z.ColorSwitch, z.ColorSwitch_SupportedReport),
    (z.Protection, z.Protection_Report),
    (z.NodeNaming, z.NodeNaming_Report),
    (z.NodeNaming, z.NodeNaming_LocationReport),
    (z.TimeParameters, z.TimeParameters_Report),
    (z.Lock, z.Lock_Report),
    (z.Indicator, z.Indicator_Report),
    (z.SwitchMultilevel, z.SwitchMultilevel_StopLevelChange),
    (z.WakeUp, z.WakeUp_IntervalCapabilitiesReport),
    (z.SwitchMultilevel, z.SwitchMultilevel_SupportedReport),
    (z.DoorLock, z.DoorLock_Report),
    (z.DoorLockLogging, z.DoorLockLogging_SupportedReport),
    (z.UserCode, z.UserCode_NumberReport),
    # set - a few requests may actually be sent to the controller
    (z.Basic, z.Basic_Set),
    (z.SceneActivation, z.SceneActivation_Set),
    (z.Clock, z.Clock_Report),
]


_STORE_VALUE_RAW_ACTIONS = [
    (z.Alarm, z.Alarm_SupportedReport),
    (z.Powerlevel, z.Powerlevel_Report),
    (z.SensorAlarm, z.SensorAlarm_SupportedReport),
    (z.ThermostatMode, z.ThermostatMode_Report),
    # needs work
    (z.ManufacturerSpecific, z.ManufacturerSpecific_DeviceSpecificReport),
    (z.ApplicationStatus, z.ApplicationStatus_Busy),
    (z.MultiInstance, z.MultiInstance_ChannelEndPointReport),
    (z.SwitchMultilevel, z.SwitchMultilevel_StartLevelChange),
    (z.DoorLock, z.DoorLock_ConfigurationReport),
    (z.ZwavePlusInfo, z.ZwavePlusInfo_Report),
    (z.Version, z.Version_Report),
    (z.ManufacturerSpecific, z.ManufacturerSpecific_Report),
    (z.Firmware, z.Firmware_MetadataReport),
]


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


def ValueLevel(kind, values):
    return Value(kind, UNIT_LEVEL, values["level"])


def ValueLevelImmediate(kind, immediate):
    return Value(kind, UNIT_LEVEL, immediate)


def ValueSensorNormal(values):
    kind = values["type"]
    info = SENSOR_TYPES[kind]
    v = values["value"]
    scale = v["scale"]
    reading = v["_value"]
    unit = info[1][scale]

    assert unit is not None
    return Value(info[0], unit, reading)


def ValueMeterNormal(values):
    v = values["meter"]
    kind = v["type"]
    scale = v["unit"]
    info = METER_TYPES[kind]
    unit = info[1][scale]
    assert unit is not None
    return Value(info[0], unit, v["_value"], v["dt"], v["_value2"])


def ValueBare(k, value):
    return Value(GetValueName(k), UNIT_NONE, value)


def RenderSensorList(values):
    return str([SENSOR_TYPES[x][0] for x in values])


def RenderMeterList(meter, values):
    return str([METER_TYPES[meter][1][x] for x in values])


# for event triggering
VALUE_CHANGERS = {
    (z.SceneActuatorConf, z.SceneActuatorConf_Report),
    (z.Version, z.Version_CommandClassReport),
    (z.SensorMultilevel, z.SensorMultilevel_Report),
    (z.SensorMultilevel, z.SensorMultilevel_SupportedReport),
    (z.SwitchBinary, z.SwitchBinary_Report),
    (z.Battery, z.Battery_Report),
    (z.SensorBinary, z.SensorBinary_Report),
    (z.SwitchToggleBinary, z.SwitchToggleBinary_Report),
    (z.SwitchMultilevel, z.SwitchMultilevel_Report),
    (z.Basic, z.Basic_Report),
    (z.Meter, z.Meter_Report),
    (z.Meter, z.Meter_SupportedReport),
    (z.Configuration, z.Configuration_Report),
    (z.Association, z.Association_GroupingsReport),
    (z.Association, z.Association_Report),
    (z.AssociationGroupInformation, z.AssociationGroupInformation_NameReport),
    (z.AssociationGroupInformation, z.AssociationGroupInformation_InfoReport),
    (z.AssociationGroupInformation, z.AssociationGroupInformation_ListReport),
    (z.ColorSwitch, z.ColorSwitch_Report),
}

# ======================================================================
# This is the main dispatch table for incoming "commands", e.g. reports
# ======================================================================
ACTIONS = {
    (z.SceneActuatorConf, z.SceneActuatorConf_Report):
        lambda n, k0, k1, v: None,
    #
    # COMMAND
    #
    (z.Version, z.Version_CommandClassReport):
        lambda n, k0, k1, v: n.commands.SetVersion(v),
    #
    # SENSOR
    #
    (z.SensorMultilevel, z.SensorMultilevel_Report):
        lambda n, k0, k1, v: n.sensors.Set(ValueSensorNormal(v)),
    (z.SensorMultilevel, z.SensorMultilevel_SupportedReport):
        lambda n, k0, k1, v: n.sensors.SetSupported(v),
    (z.SwitchBinary, z.SwitchBinary_Report):
        lambda n, k0, k1, v: n.sensors.Set(ValueLevel(SENSOR_KIND_SWITCH_BINARY, v)),
    (z.Battery, z.Battery_Report):
        lambda n, k0, k1, v: n.sensors.Set(ValueLevel(SENSOR_KIND_BATTERY, v)),
    (z.SensorBinary, z.SensorBinary_Report):
        lambda n, k0, k1, v: n.sensors.Set(ValueLevel(SENSOR_KIND_SWITCH_BINARY, v)),
    (z.SwitchToggleBinary, z.SwitchToggleBinary_Report):
        lambda n, k0, k1, v: n.sensors.Set(ValueLevel(SENSOR_KIND_SWITCH_TOGGLE, v)),
    (z.SwitchMultilevel, z.SwitchMultilevel_Report):
        lambda n, k0, k1, v: n.sensors.Set(ValueLevel(SENSOR_KIND_SWITCH_MULTILEVEL, v)),
    (z.Basic, z.Basic_Report):
        lambda n, k0, k1, v: n.sensors.Set(ValueLevel(SENSOR_KIND_BASIC, v)),
    #
    # METER
    #
    (z.Meter, z.Meter_Report):
        lambda n, k0, k1, v: n.meters.Set(ValueMeterNormal(v)),
    (z.Meter, z.Meter_SupportedReport):
        lambda n, k0, k1, v: n.meters.SetSupported(v),
    #
    # PARAMETER
    #
    (z.Configuration, z.Configuration_Report):
        lambda n, k0, k1, v: n.parameters.Set(v),
    #
    # ASSOCIATIONS
    #
    (z.Association, z.Association_GroupingsReport):
        lambda n, k0, k1, v: n.associations.StoreCount(v),
    (z.Association, z.Association_Report):
        lambda n, k0, k1, v: n.associations.StoreNodes(v),
    (z.AssociationGroupInformation, z.AssociationGroupInformation_NameReport):
        lambda n, k0, k1, v: n.associations.StoreName(v),
    (z.AssociationGroupInformation, z.AssociationGroupInformation_InfoReport):
        lambda n, k0, k1, v: n.associations.StoreMeta(v),
    (z.AssociationGroupInformation, z.AssociationGroupInformation_ListReport):
        lambda n, k0, k1, v: n.associations.StoreCommands(v),
    #
    # MAP VALUES
    #
    (z.ColorSwitch, z.ColorSwitch_Report):
        lambda n, k0, k1, v: n.values.SetMap(k, ValueBare(k, {v[0]: v[1]})),
    #
    #
    # EVENTS
    #
    (z.Alarm, z.Alarm_Report):
        lambda n, k0, k1, v: n.StoreEvent(ValueLevel(EVENT_ALARM, v)),
    (z.Alarm, z.Alarm_Set):
        lambda n, k0, k1, v: n.StoreEvent(Value(EVENT_ALARM, UNIT_NONE, v)),
    (z.WakeUp, z.WakeUp_Notification):
        lambda n, k0, k1, v: n.StoreEvent(Value(EVENT_WAKE_UP, UNIT_NONE, 1)),
    #
    # These need a lot more work
    #
    # (zwave.py.Security, zwave.py.Security_SchemeReport): [SECURITY_SCHEME],
    # (zwave.py.Security, zwave.py.Security_NonceReport): [SECURITY_NONCE_RECEIVED],
    # (zwave.py.Security, zwave.py.Security_NonceGet): [SECURITY_NONCE_REQUESTED],
    # (zwave.py.Security, zwave.py.Security_SupportedReport): [SECURITY_SET_CLASS],
    # (zwave.py.Security, zwave.py.Security_MessageEncap): [SECURITY_UNWRAP],
    # (zwave.py.Security, zwave.py.Security_NetworkKeyVerify): [SECURITY_KEY_VERIFY],

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
    (z.ManufacturerSpecific, z.ManufacturerSpecific_Report): NODE_STATE_INTERVIEWED,
}

NO_ACTION = None, None, None


def GetSingleScalar(k0, k1, args):
    table = z.SUBCMD_TO_PARSE_TABLE[k0 * 256 + k1]
    assert len(table) == 1
    name = table[0][2:-1]
    return args[name]

def PatchUpActions():
    global ACTIONS
    logging.info("PatchUpActions")
    for key in _STORE_VALUE_SCALAR_ACTIONS:
        ACTIONS[key] = lambda n, k0, k1, v: n.values.Set(
            (k0, k1), ValueBare((k0, k1), GetSingleScalar(k0, k1, v)))

    for key in _STORE_VALUE_RAW_ACTIONS:
        ACTIONS[key] = lambda n, k0, k1, v: n.values.Set((k0, k1), v)


PatchUpActions()
