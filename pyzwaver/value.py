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
import traceback

from pyzwaver import zwave as z

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
SENSOR_KIND_TEMPERATURE = "Temperature"
SENSOR_KIND_UNKNOWN = "Unknown"
#
SECURITY_SET_CLASS = "SecuritySetClass"
SECURITY_SCHEME = "SecurityScheme"
SECURITY_NONCE_RECEIVED = "SecurityNonceReceived"
SECURITY_NONCE_REQUESTED = "SecurityNonceRequested"
SECURITY_UNWRAP = "SecurityUnwrap"
SECURITY_KEY_VERIFY = "SecurityKeyVerify"


def GetSingleScalar(key, args):
    table = z.SUBCMD_TO_PARSE_TABLE[key[0] * 256 + key[1]]
    assert len(table) == 1
    name = table[0][2:-1]
    return args[name]


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
    [SENSOR_KIND_TEMPERATURE, ["C", "F", None, None]],
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
SENSOR_VALUES = {
    # (z.SensorMultilevel, z.SensorMultilevel_Report),
    z.SwitchBinary_Report,
    z.Battery_Report,
    z.SensorBinary_Report,
    z.SwitchToggleBinary_Report,
    z.SwitchMultilevel_Report,
    z.Basic_Report,
}

EVENT_VALUES = [
    z.Alarm_Report,
    z.Alarm_Set,
    z.WakeUp_Notification,
    z.Basic_Get,
    z.Hail_Hail,
]

# for event triggering
VALUE_CHANGERS = {
    z.SceneActuatorConf_Report,
    z.Version_CommandClassReport,
    z.SensorMultilevel_Report,
    z.SensorMultilevel_SupportedReport,
    z.SwitchBinary_Report,
    z.Battery_Report,
    z.SensorBinary, z.SensorBinary_Report,
    z.SwitchToggleBinary, z.SwitchToggleBinary_Report,
    z.SwitchMultilevel, z.SwitchMultilevel_Report,
    z.Basic_Report,
    z.Meter_Report,
    z.Meter_SupportedReport,
    z.Configuration_Report,
    z.Association_GroupingsReport,
    z.Association_Report,
    z.AssociationGroupInformation_NameReport,
    z.AssociationGroupInformation_InfoReport,
    z.AssociationGroupInformation_ListReport,
    z.ColorSwitch_Report,
}


def GetSensorMeta(kind, unit):
    try:
        info = SENSOR_TYPES[kind]
        return info[0], info[1][unit]
    except BaseException:
        logging.error("bad sensorunit/type in: %d %d", kind, unit)
        print("-" * 60)
        traceback.print_exc(file=sys.stdout)
        print("-" * 60)
        return SENSOR_KIND_UNKNOWN, "unknown unit"


def GetMeterMeta(kind, unit):
    try:
        info = METER_TYPES[kind]
        return info[0], info[1][unit]
    except BaseException as e:
        logging.error("bad meterunit/type in: %d %d (%s)",
                      kind, unit, str(e))
        print("-" * 60)
        traceback.print_exc(file=sys.stdout)
        print("-" * 60)
        return SENSOR_KIND_UNKNOWN, "unknown unit"


def CompactifyParams(params):
    out = []
    last = [-1, -1, -1, -1]  # range start, range end, size, value
    for k, a, b in sorted(params):
        if last[2] != a or last[3] != b or last[1] != k - 1:
            last = [k, k, a, b]
            out.append(last)
        else:
            last[1] = k  # increment range end
    return out
