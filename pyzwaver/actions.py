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

from pyzwaver import zwave as z

NODE_STATE_NONE = "0_None"
NODE_STATE_INCLUDED = "1_Included"
# discovered means we have the command classes
NODE_STATE_DISCOVERED = "2_Discovered"
# interviewed means we have received product info (including most static
# info an versions)
NODE_STATE_INTERVIEWED = "3_Interviewed"

# ======================================================================
NORMAL_VALUES = [
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
    (z.SensorMultilevel, z.SensorMultilevel_SupportedReport),
    (z.Meter, z.Meter_SupportedReport),
    (z.Association, z.Association_GroupingsReport),
    #
    # TODO
    #
    (z.ColorSwitch, z.ColorSwitch_Report),  # may need a map
    (z.SceneActuatorConf, z.SceneActuatorConf_Report),

]

SENSOR_VALUES = [
    # (z.SensorMultilevel, z.SensorMultilevel_Report),
    (z.SwitchBinary, z.SwitchBinary_Report),
    (z.Battery, z.Battery_Report),
    (z.SensorBinary, z.SensorBinary_Report),
    (z.SwitchToggleBinary, z.SwitchToggleBinary_Report),
    (z.SwitchMultilevel, z.SwitchMultilevel_Report),
    (z.Basic, z.Basic_Report),
]

EVENT_VALUES = [
    (z.Alarm, z.Alarm_Report),
    (z.Alarm, z.Alarm_Set),
    (z.WakeUp, z.WakeUp_Notification),
]

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


def _CommandSubkey(v):
    return v["class"]


def _MeterSubkey(v):
    return v["meter"]["type"], v["meter"]["unit"]


def _ConfigurationSubkey(v):
    return v["parameter"]


def _SensorSubkey(v):
    return v["type"], v["value"]["scale"]


def _AssociationSubkey(v):
    return v["group"]


# ======================================================================
# This is the main dispatch table for incoming "commands", e.g. reports
# ======================================================================
ACTIONS = {
    (z.Version, z.Version_CommandClassReport):
        lambda n, k0, k1, v: n.values.SetMapEntry((k0, k1), _CommandSubkey(v), v),

    (z.Meter, z.Meter_Report):
        lambda n, k0, k1, v: n.values.SetMapEntry((k0, k1), _MeterSubkey(v), v),

    (z.Configuration, z.Configuration_Report):
        lambda n, k0, k1, v: n.values.SetMapEntry((k0, k1), _ConfigurationSubkey(v), v),

    (z.SensorMultilevel, z.SensorMultilevel_Report):
        lambda n, k0, k1, v: n.values.SetMapEntry((k0, k1), _SensorSubkey(v), v),

    (z.Association, z.Association_Report):
        lambda n, k0, k1, v: n.values.SetMapEntry((k0, k1), _AssociationSubkey(v), v),
    (z.AssociationGroupInformation, z.AssociationGroupInformation_NameReport):
        lambda n, k0, k1, v: n.values.SetMapEntry((k0, k1), _AssociationSubkey(v), v),
    (z.AssociationGroupInformation, z.AssociationGroupInformation_InfoReport):
        lambda n, k0, k1, v: n.values.SetMapEntry((k0, k1), _AssociationSubkey(v), v),
    (z.AssociationGroupInformation, z.AssociationGroupInformation_ListReport):
        lambda n, k0, k1, v: n.values.SetMapEntry((k0, k1), _AssociationSubkey(v), v),

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


def StringifyCommamnd(cmd0, cmd1):
    return z.SUBCMD_TO_STRING.get(cmd0 * 256 + cmd1, "Unknown_%02x:%02x" % (cmd0, cmd1))


def PatchUpActions():
    global ACTIONS
    logging.info("PatchUpActions")
    for key in SENSOR_VALUES:
        assert key not in ACTIONS, StringifyCommamnd(*key)
        ACTIONS[key] = lambda n, k0, k1, v: n.values.Set((k0, k1), v)

    for key in EVENT_VALUES:
        assert key not in ACTIONS, StringifyCommamnd(*key)
        ACTIONS[key] = lambda n, k0, k1, v: n.values.Set((k0, k1), v)

    for key in NORMAL_VALUES:
        assert key not in ACTIONS, StringifyCommamnd(*key)
        ACTIONS[key] = lambda n, k0, k1, v: n.values.Set((k0, k1), v)


PatchUpActions()
