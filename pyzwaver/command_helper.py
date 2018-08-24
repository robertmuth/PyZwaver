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
from pyzwaver import zwave as z

DYNAMIC_PROPERTY_QUERIES = [
    # Basic should be first
    (z.Basic_Get, {}),
    (z.Alarm_Get, {}),
    (z.SensorBinary_Get, {}),
    (z.Battery_Get, {}),

    (z.Lock_Get, {}),
    (z.DoorLock_Get, {}),

    (z.Powerlevel_Get, {}),
    (z.Protection_Get, {}),
    # (zwave.SensorBinary, zwave.SensorBinary_Get, {}),
    (z.SwitchBinary_Get, {}),
    (z.SwitchMultilevel_Get, {}),
    (z.SwitchToggleBinary_Get, {}),
    # only v5 offer the extra parameter
    (z.Indicator_Get, {}),
    # get the current scene
    (z.SceneActuatorConf_Get, {"scene": 0}),
    (z.SensorAlarm_Get, {}),
    (z.ThermostatMode_Get, {})
]

STATIC_PROPERTY_QUERIES = [
    (z.SensorMultilevel_SupportedGet, {}),

    (z.UserCode_NumberGet, {}),
    (z.DoorLock_ConfigurationGet, {}),
    (z.DoorLockLogging_SupportedGet, {}),

    (z.Meter_SupportedGet, {}),
    (z.SensorAlarm_SupportedGet, {}),
    (z.ThermostatMode_SupportedGet, {}),
    (z.ThermostatSetpoint_SupportedGet, {}),
    (z.Version_Get, {}),
    (z.SwitchMultilevel_SupportedGet, {}),
    (z.MultiChannel_EndPointGet, {}),

    # device type
    (z.ManufacturerSpecific_DeviceSpecificGet, {"type": 0}),
    # serial no
    (z.ManufacturerSpecific_DeviceSpecificGet, {"type": 1}),

    (z.TimeParameters_Get, {}),
    (z.ZwavePlusInfo_Get, {}),
    (z.SwitchAll_Get, {}),
    (z.Alarm_SupportedGet, {}),
    # mostly static
    # zwave.AssociationCommandConfiguration_SupportedGet],
    (z.NodeNaming_Get, {}),
    (z.NodeNaming_LocationGet, {}),
    (z.ColorSwitch_SupportedGet, {}),
    # arguably dynamic
    (z.Clock_Get, {}),
    (z.Firmware_MetadataGet, {}),
    (z.CentralScene_SupportedGet, {}),
    (z.Association_GroupingsGet, {}),
]


def SensorMultiLevelQueries(sensors):
    # older version
    return ([(z.SensorMultilevel_Get, {})] +
            [(z.SensorMultilevel_Get, {"sensor": s}) for s in sensors])


def MeterQueries(scales=(0, 1, 2, 3)):
    # older versions
    return ([(z.Meter_Get, {})] +
            # newer versions
            [(z.Meter_Get, {"scale": s << 3}) for s in scales])


def ColorQueries(groups):
    return [(z.ColorSwitch_Get, {"group": g}) for g in groups]


def CommandVersionQueries(classes):
    return [(z.Version_CommandClassGet, {"class": c}) for c in classes]


def MultiChannelEndpointQueries(endpoints):
    return [(z.MultiChannel_CapabilityGet, {"mode": 0, "endpoint": e}) for e in endpoints]


def SceneActuatorConfiguration(scenes):
    return [(z.SceneActuatorConf_Get, {"scene": s}) for s in scenes]


def ParameterQueries(params):
    return [(z.Configuration_Get, {"parameter": p}) for p in params]


def AssociationQueries(assocs):
    c = []
    for no in assocs:
        v = {"group": no}
        c.append((z.Association_Get, v))
        c.append((z.AssociationGroupInformation_NameGet, v))
        v = {"group": no, "mode": 0}
        c.append((z.AssociationGroupInformation_ListGet, v))
        c.append((z.AssociationGroupInformation_InfoGet, v))
    return c


def BinarySwitchSet(val, request_update=True):
    c = [(z.SwitchBinary_Set, {"level": val})]
    if request_update:
        c += [(z.SwitchBinary_Get, {}),
              (z.SwitchMultilevel_Get, {})]
    return c


def SceneActuatorConfSet(scene, delay, extra, level, request_update=True):
    c = [(z.SceneActuatorConf_Set,
         {"scene": scene, "delay": delay, "extra": extra, "level": level})]
    if request_update:
        c += [(z.SceneActuatorConf_Get, {"scene": scene})]
    return c


def ResetMeter(_request_update=True):
    # TODO
    c = [(z.Meter_Reset, {})]
    # if not request_update:
    #    c += [(z.Meter_Get, {})]
    return c


def BasicSet(val, request_update=True):
    c = [(z.Basic_Set, {"level": val})]
    if request_update:
        c += [(z.Basic_Get, {})]
    return c


# Version 1 of the command class does not support `delay`
def MultilevelSwitchSet(val, delay=0, request_update=True):
    c = [(z.SwitchMultilevel_Set, {"level": val, "duration": delay})]
    if request_update:
        c += [(z.SwitchBinary_Get, {}),
              (z.SwitchMultilevel_Get, {})]
    return c


def ConfigurationSet(param, size, val, request_update=True):
    c = [(z.Configuration_Set,
          {"parameter": param, "value": {"size": size, "value": val}})]
    if request_update:
        c += [(z.Configuration_Get, {"parameter": param})]
    return c


def AssociationAdd(group, n):
    return [(z.Association_Set, {"group": group, "nodes": [n]}),
            (z.Association_Get, {"group": group})]


def AssociationRemove(group, n):
    return [(z.Association_Remove, {"group": n, "nodes": [n]}),
            (z.Association_Get, {"group": group})]
