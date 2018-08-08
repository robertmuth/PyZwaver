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
import time

from pyzwaver import zmessage
from pyzwaver import actions
from pyzwaver import zwave as z
from pyzwaver import protocol_node
from pyzwaver import command


def Hexify(t):
    return ["%02x" % i for i in t]


XMIT_OPTIONS_NO_ROUTE = (z.TRANSMIT_OPTION_ACK |
                         z.TRANSMIT_OPTION_EXPLORE)

XMIT_OPTIONS = (z.TRANSMIT_OPTION_ACK |
                z.TRANSMIT_OPTION_AUTO_ROUTE |
                z.TRANSMIT_OPTION_EXPLORE)

XMIT_OPTIONS_SECURE = (z.TRANSMIT_OPTION_ACK |
                       z.TRANSMIT_OPTION_AUTO_ROUTE)

_DYNAMIC_PROPERTY_QUERIES = [
    # Basic should be first
    (z.Basic, z.Basic_Get, {}),
    (z.Alarm, z.Alarm_Get , {}),
    (z.SensorBinary, z.SensorBinary_Get, {}),
    (z.Battery, z.Battery_Get, {}),

    (z.Lock, z.Lock_Get, {}),
    (z.DoorLock, z.DoorLock_Get, {}),

    (z.Powerlevel, z.Powerlevel_Get, {}),
    (z.Protection, z.Protection_Get, {}),
    # (zwave.SensorBinary, zwave.SensorBinary_Get, {}),
    (z.SwitchBinary, z.SwitchBinary_Get, {}),
    (z.SwitchMultilevel, z.SwitchMultilevel_Get, {}),
    (z.SwitchToggleBinary, z.SwitchToggleBinary_Get, {}),
    # only v5 offer the extra parameter
    (z.Indicator, z.Indicator_Get, {}),
    # get the current scene
    (z.SceneActuatorConf, z.SceneActuatorConf_Get, {"scene": 0}),
    (z.SensorAlarm, z.SensorAlarm_Get, {}),
    (z.ThermostatMode, z.ThermostatMode_Get, {})
]


def SensorMultiLevelQueries(sensors):
    # older version
    return ([(z.SensorMultilevel, z.SensorMultilevel_Get, {})] +
            [(z.SensorMultilevel, z.SensorMultilevel_Get, {"sensor": s})
             for s in sensors])


def DynamicPropertyQueriesMultiInstance(instances):
    out = []
    for i in instances:
        out.append((z.MultiInstance, z.MultiInstance_Encap, {
            "mode": i,
            "command": [z.SensorMultilevel, z.SensorMultilevel_Get]}))
    return out


def MeterQueries(scales=(0, 1, 2, 3)):
    # older versions
    return ([(z.Meter, z.Meter_Get, {})] +
            # newer versions
            [(z.Meter, z.Meter_Get, {"scale": s << 3}) for s in scales])


_STATIC_PROPERTY_QUERIES = [
    (z.SensorMultilevel, z.SensorMultilevel_SupportedGet, {}),

    (z.UserCode, z.UserCode_NumberGet, {}),
    (z.DoorLock, z.DoorLock_ConfigurationGet, {}),
    (z.DoorLockLogging, z.DoorLockLogging_SupportedGet, {}),

    (z.Meter, z.Meter_SupportedGet, {}),
    (z.SensorAlarm, z.SensorAlarm_SupportedGet, {}),
    (z.ThermostatMode, z.ThermostatMode_SupportedGet, {}),
    (z.ThermostatSetpoint, z.ThermostatSetpoint_SupportedGet, {}),
    (z.Version, z.Version_Get, {}),
    (z.SwitchMultilevel, z.SwitchMultilevel_SupportedGet, {}),
    (z.MultiInstance, z.MultiInstance_ChannelEndPointGet, {}),

    # device type
    (z.ManufacturerSpecific, z.ManufacturerSpecific_DeviceSpecificGet, {"type": 0}),
    # serial no
    (z.ManufacturerSpecific, z.ManufacturerSpecific_DeviceSpecificGet, {"type": 1}),

    (z.TimeParameters, z.TimeParameters_Get, {}),
    (z.ZwavePlusInfo, z.ZwavePlusInfo_Get, {}),
    (z.SwitchAll, z.SwitchAll_Get, {}),
    (z.Alarm, z.Alarm_SupportedGet, {}),
    # mostly static
    # [zwave.AssociationCommandConfiguration, zwave.AssociationCommandConfiguration_SupportedGet],
    (z.NodeNaming, z.NodeNaming_Get, {}),
    (z.NodeNaming, z.NodeNaming_LocationGet, {}),
    (z.ColorSwitch, z.ColorSwitch_SupportedGet, {}),
    # arguably dynamic
    (z.Clock, z.Clock_Get, {}),
    (z.Firmware, z.Firmware_MetadataGet, {}),
    (z.Association, z.Association_GroupingsGet, {}),
    (z.AssociationGroupInformation, z.AssociationGroupInformation_InfoGet, {"mode": 64, "group": 0}),
]


def ColorQueries(groups):
    return [(z.ColorSwitch, z.ColorSwitch_Get, {"group": g}) for g in groups]


def CommandVersionQueries(classes):
    return [(z.Version, z.Version_CommandClassGet, {"class": c}) for c in classes]


def MultiInstanceSupportQueries(classes):
    return [(z.MultiInstance, z.MultiInstance_Get, {"mode": c}) for c in classes]


def BitsToSetWithOffset(x, offset):
    out = set()
    pos = 0
    while x:
        if (x & 1) == 1:
            out.add(pos + offset)
        pos += 1
        x >>= 1
    return out


def RenderValues(values):
    return str([str(v) for v in sorted(values)])


def CompactifyParams(params):
    out = []
    last = [-1, -1, -1, -1]  # range start, range end, size, value
    for k in sorted(params.keys()):
        a, b = params[k]
        if last[2] != a or last[3] != b or last[1] != k - 1:
            last = [k, k, a, b]
            out.append(last)
        else:
            last[1] = k  # increment range end
    return out


class AssociationGroup:
    """
    """

    def __init__(self, no):
        self._no = no
        self.nodes = []
        self.capacity = 0
        self.name = ""
        self._profile = None
        self._event = None
        self._commands = None

    def SetNodes(self, capacity, nodes):
        self.capacity = capacity
        self.nodes = nodes

    def SetMeta(self, profile, event):
        self._profile = profile
        self._event = event

    def SetName(self, name):
        self.name = name

    def SetCommands(self, commands):
        self._commands = commands

    def __str__(self):
        return "Group %d [%s]  profile:%d  event:%d  cmds:%s  capacity:%d  nodes:%s" % (
            self._no, self.name, self._profile, self._event, self._commands, self.capacity, self.nodes)


class NodeAssociations:
    """
    """

    def __init__(self):
        self._groups = {}
        self._count = -1

    def GetGroup(self, no):
        g = self._groups.get(no)
        if g is not None:
            return g
        g = AssociationGroup(no)
        self._groups[no] = g
        return g

    def Groups(self):
        ordered = sorted([x for x in self._groups.items()])
        return [g for _, g in ordered]

    def StoreCount(self, values):
        self._count = values["count"]

    def StoreNodes(self, val):
        # we do not support extra long lists
        no = val[0]
        capacity = val[1]
        assert val[2] == 0
        nodes = val[3]
        self.GetGroup(no).SetNodes(capacity, nodes)

    def StoreName(self, val):
        no = val[0]
        name = val[1]
        self.GetGroup(no).SetName(name)

    def StoreCommands(self, val):
        no = val[0]
        commands = val[1]
        self.GetGroup(no).SetCommands(commands)

    def StoreMeta(self, val):
        for no, profile, event in val[0]:
            self.GetGroup(no).SetMeta(profile, event)

    def GetNumbers(self):
        if len(self._groups) > 0:
            return self._groups.keys()
        n = self._count
        if n == 0 or n == 255:
            n = 4
        return list(range(1, n + 1)) + [255]

    def __str__(self):
        return "\n".join([str(g) for g in self._groups.values()])


class NodeCommands:

    def __init__(self):
        self._version_map = {}
        self._controls = set()

    def Classes(self):
        return self._version_map.keys()

    def CommandVersions(self):
        return sorted([x for x in self._version_map.items()])

    def HasCommandClass(self, cls):
        return cls in self._version_map

    def NumCommands(self):
        return len(self._version_map)

    def HasAlternaticeForBasicCommand(self):
        return (z.SwitchBinary in self._version_map or
                z.SwitchMultilevel in self._version_map)

    def SetVersion(self, values):
        version = values["version"]
        if version == 0:
            return
        self._version_map[values["class"]] = version

    def InitializeUnversioned(self, cmd, controls, std_cmd, std_controls):
        self._controls |= set(controls)
        self._controls |= set(std_controls)

        for k in cmd:
            if k not in self._version_map:
                self._version_map[k] = -1
        for k in controls:
            if k not in self._version_map:
                self._version_map[k] = -1
        for k in std_cmd:
            if k not in self._version_map:
                self._version_map[k] = -1

        k = z.MultiInstance
        if k in self._controls and k not in self._version_map:
            self._version_map[k] = -1

    def __str__(self):
        return repr([(z.CMD_TO_STRING.get(c, "UKNOWN:%d" % c), c, v)
                     for c, v in self._version_map.items()])


class NodeParameters:
    def __init__(self):
        self._parameters = {}

    def Set(self, values):
        self._parameters[values[0]] = values[1]

    def __str__(self):
        return repr(CompactifyParams(self._parameters))


VALUE_KEY_MULTILEVEL_SWITCH = (actions.SENSOR_KIND_SWITCH_MULTILEVEL, actions.UNIT_LEVEL)


class NodeSensors:
    def __init__(self):
        self._readings = {
            VALUE_KEY_MULTILEVEL_SWITCH:
                actions.ValueLevelImmediate(actions.SENSOR_KIND_SWITCH_MULTILEVEL, 0),
        }
        self._supported = set()

    def Readings(self): return self._readings.values()

    def SetSupported(self, values):
        self._supported = BitsToSetWithOffset(values["bits"]["value"], 1)

    def Supported(self):
        return self._supported

    def Set(self, val):
        if val is None:
            return
        self._readings[(val.kind, val.unit)] = val

    def HasContent(self):
        return self._supported or self._readings

    def GetMultilevelSwitchLevel(self):
        p = self._readings.get(VALUE_KEY_MULTILEVEL_SWITCH)
        return p.value

    def __str__(self):
        return ("  sensors supp.:" + actions.RenderSensorList(self._supported) +
                "  sensors:      " + RenderValues(self._readings.values()))


class NodeMeters:
    def __init__(self):
        self._readings = {}
        self._flags = 0
        self._supported = set()

    def Readings(self): return self._readings.values()

    def HasContent(self):
        return self._supported or self._readings

    def SetSupported(self, values):
        self._flags = values["type"]
        self._supported = BitsToSetWithOffset(values["scale"], 0)

    def Supported(self):
        return self._supported

    def Resetable(self):
        return (self._flags & 0x80) != 0

    def Set(self, val):
        if val is None:
            return
        self._readings[(val.kind, val.unit)] = val

    def __str__(self):
        return ("  meters supp.:" + actions.RenderMeterList(self._flags & 0x1f, self._supported) +
                "  meters:      " + RenderValues(self._readings.values()))


KEY_VERSION = (z.Version, z.Version_Report)
KEY_MANUFACTURER_SPECIFIC = (z.ManufacturerSpecific, z.ManufacturerSpecific_Report)
KEY_COLOR_SWITCH_SUPPORTED = (z.ColorSwitch, z.ColorSwitch_SupportedReport)


class NodeValues:
    def __init__(self):
        self._values = {
            KEY_VERSION:
                (-1.0, actions.ValueBare(KEY_VERSION, [-1, 0, 0, 0, 0])),
            KEY_MANUFACTURER_SPECIFIC:
                (-1.0, actions.ValueBare(KEY_MANUFACTURER_SPECIFIC, [0, 0, 0])),
            KEY_COLOR_SWITCH_SUPPORTED:
                (-1.0, actions.ValueBare(KEY_COLOR_SWITCH_SUPPORTED, set())),
        }

    def HasValue(self, key: tuple):
        return key in self._values

    def Set(self, key, value):
        if value is None:
            return
        self._values[key] = time.time(), value

    def SetMap(self, key: tuple, value):
        if value is None:
            return
        _, v = self._values.get(key, (None, None))
        if v is None:
            v = value
        else:
            v.value.update(value.value)
        self._values[key] = time.time(), v

    def Get(self, key: tuple):
        v = self._values.get(key)
        if v is not None:
            return v[1]
        return None

    def GetAllTuples(self):
        return sorted([(k, v[0], v[1]) for k, v in self._values.items() if v[0]])

    def __str__(self):
        return RenderValues(self._values.values())


class ApplicationNode:
    """Node represents a single node in a zwave network.

    The message_queue (_shared.mq) is used to send messages to the node.
    Message from the node are send to the NodeSet first which dispatches them
    to the relevant Node by calling ProcessCommand() or ProcessNodeInfo().
    """

    def __init__(self, n, protocol_node: protocol_node.Node):
        assert n >= 1
        self.n = n
        self.name = "Node %d" % n
        self._protocol_node = protocol_node
        self._state = actions.NODE_STATE_NONE
        #
        self.commands = NodeCommands()
        self._secure_commands = NodeCommands()
        self.values = NodeValues()
        self.meters = NodeMeters()
        self.sensors = NodeSensors()
        self.parameters = NodeParameters()
        self.associations = NodeAssociations()
        self._events = {}
        self.scenes = {}
        self.awake = True

    def ProductInfo(self):
        p = self.values.Get(KEY_MANUFACTURER_SPECIFIC)
        return tuple(p.value)

    def LibraryType(self):
        p = self.values.Get(KEY_VERSION)
        return p.value[0]

    def SDKVersion(self):
        p = self.values.Get(KEY_VERSION)
        return p.value[1], p.value[2]

    def ApplicationVersion(self):
        p = self.values.Get(KEY_VERSION)
        return p.value[3], p.value[4]

    def __lt__(self, other):
        return self.n < other.n

    def BasicString(self):
        out = [
            "NODE: %d" % self.n,
            "state: %s" % self._state,
            "lib_type: %s" % self.LibraryType(),
            "sdk_version: %d:%d" % self.SDKVersion(),
            "app_version: %d:%d" % self.ApplicationVersion(),
            "product: %04x:%04x:%04x" % self.ProductInfo(),
        ]
        return "  ".join(out)

    def __str__(self):
        out = [self.BasicString()]
        # self._values.get(VALUE_PROUCT, DEFAULT_PRODUCT))
        #         out.append("  control: %s" % (
        #             [(zwave_cmd.CommandToString(c)) for c in self.control]))
        #         out.append("  configuration: " + repr(self.configuration))
        #         out.append("  scenes:       " + repr(self.scenes))
        #         meter = {zwave_cmd.GetMeterUnits(*k): v for k, v in self.meter.items()}
        # sensor = {zwave_cmd.GetSensorUnits(*k): v for k, v in
        # self.sensor.items()}
        if self.meters.HasContent():
            out.append(str(self.meters))
        if self.sensors.HasContent():
            out.append(str(self.sensors))
        out.append("  values:")
        out.append(str(self.values))
        out.append("  events:       " + repr(self._events))
        out.append("  parameters:")
        out.append(str(self.parameters))
        out.append("  commands:")
        out.append(str(self.commands))
        out.append("  associations:")
        out.append(str(self.associations))
        return "\n".join(out)

    def BasicInfo(self):
        return {
            "#": self.n,
            "state": self._state[2:],
            # "device": "%02d:%02d:%02d" % self.device_type,
            "product": "0x%04x:0x%04x:0x%04x  " % self.ProductInfo(),
            "sdk_version": "%d:%d" % self.SDKVersion(),
            "app_version": "%d:%d" % self.ApplicationVersion(),
            "lib_type": self.LibraryType(),
        }

    def BatchCommandSubmitFiltered(self, commands, priority: tuple, xmit : int):
        for c in commands:
            if len(c) != 3:
                logging.error("BAD COMMAND: %s", c)
                assert False

        for key0, key1, values in commands:
            if not self.commands.HasCommandClass(key0):
                continue

            # if self._IsSecureCommand(cmd[0], cmd[1]):
            #    self._secure_messaging.Send(cmd)
            #    continue

            self._protocol_node.SendCommand(key0, key1, values, priority, xmit)

    def BatchCommandSubmitFilteredSlow(self, commands, xmit):
        self.BatchCommandSubmitFiltered(commands, zmessage.NodePriorityLo(self.n), xmit)

    def BatchCommandSubmitFilteredFast(self, commands, xmit):
        self.BatchCommandSubmitFiltered(commands, zmessage.NodePriorityHi(self.n), xmit)

    def _IsSecureCommand(self, key0, key1):
        if key0 == z.Security:
            return key1 in [z.Security_NetworkKeySet, z.Security_SupportedGet]

        return self._secure_commands.HasCommandClass(key0)

    def _InitializeSecurity(self):
        logging.error("[%d] initializing security", self.n)
        # self.RefreshStaticValues()
        self.BatchCommandSubmitFilteredSlow(
            [[z.Security, z.Security_SchemeGet, 0]], XMIT_OPTIONS)

    def _InitializeCommands(self, typ, cmd, controls):
        k = typ[1] * 256 + typ[2]
        v = z.GENERIC_SPECIFIC_DB.get(k)
        if v is None:
            logging.error("[%d] unknown generic device : ${type}", self.n)
            return
        self.commands.InitializeUnversioned(cmd, controls, v[1], v[2])

    def StoreEvent(self, val):
        self._events[val.kind] = val

    def ProbeNode(self):
        self.BatchCommandSubmitFilteredFast(
            [(z.NoOperation, z.NoOperation_Set, {})],
            XMIT_OPTIONS)

    #        cmd = zwave_cmd.MakeWakeUpIntervalCapabilitiesGet(
    #            self.n, xmit, driver.GetCallbackId())
    #        driver.Send(cmd, handler, "WakeUpIntervalCapabilitiesGet")

    def RefreshCommandVersions(self, classes):
        self.BatchCommandSubmitFilteredSlow(CommandVersionQueries(classes),
                                            XMIT_OPTIONS)

    def RefreshAllCommandVersions(self):
        self.RefreshCommandVersions(range(255))

    def RefreshSceneActuatorConfigurations(self, scenes):
        c = [(z.SceneActuatorConf, z.SceneActuatorConf_Get, {"group": s})
             for s in scenes]
        self.BatchCommandSubmitFilteredSlow(c, XMIT_OPTIONS)

    def RefreshParameters(self):
        c = [(z.Configuration, z.Configuration_Get, {"parameter": p})
             for p in range(255)]
        self.BatchCommandSubmitFilteredSlow(c, XMIT_OPTIONS)

    def SetConfigValue(self, param, size, value, request_update=True):
        reqs = [(z.Configuration, z.Configuration_Set, param, {size, value})]
        if request_update:
            reqs += [(z.Configuration, z.Configuration_Get, {param})]
        self.BatchCommandSubmitFilteredFast(reqs, XMIT_OPTIONS)

    def SetSceneConfig(self, scene, delay, extra, level, request_update=True):
        self.BatchCommandSubmitFilteredFast(
            [(z.SceneActuatorConf, z.SceneActuatorConf_Set,
              {scene, delay, extra, level})], XMIT_OPTIONS)
        if not request_update:
            return
        self.BatchCommandSubmitFilteredFast(
            [(z.SceneActuatorConf, z.SceneActuatorConf_Get, {scene})], XMIT_OPTIONS)

    def ResetMeter(self, request_update=True):
        # TODO
        c = [(z.Meter, z.Meter_Reset, {})]
        self.BatchCommandSubmitFilteredFast(c, XMIT_OPTIONS)

    def SetBasic(self, value, request_update=True):
        reqs = [(z.Basic, z.Basic_Set, {"level": value})]
        if request_update:
            reqs += [(z.Basic, z.Basic_Get, {})]
        self.BatchCommandSubmitFilteredFast(reqs, XMIT_OPTIONS)

    # Version 1 of the command class does not support `delay`
    def SetMultilevelSwitch(self, value, delay=0, request_update=True):
        reqs = [(z.SwitchMultilevel, z.SwitchMultilevel_Set, {"level": value, "duration": delay})]
        if request_update:
            reqs += [(z.SwitchBinary, z.SwitchBinary_Get, {}),
                     (z.SwitchMultilevel, z.SwitchMultilevel_Get, {})]
        self.BatchCommandSubmitFilteredFast(reqs, XMIT_OPTIONS)

    def SetBinarySwitch(self, value, request_update=True):
        reqs = [(z.SwitchBinary, z.SwitchBinary_Set, {value})]
        if request_update:
            reqs += [(z.SwitchBinary, z.SwitchBinary_Get, {}),
                     (z.SwitchMultilevel, z.SwitchMultilevel_Get, {})]
        self.BatchCommandSubmitFilteredFast(reqs, XMIT_OPTIONS)

    def RefreshAssociations(self):
        c = [(z.AssociationGroupInformation,
              z.AssociationGroupInformation_InfoGet, {64, 0})]
        for no in self.associations.GetNumbers():
            c.append((z.Association, z.Association_Get, {no}))
            c.append([z.AssociationGroupInformation,
                      z.AssociationGroupInformation_NameGet, no])
            c.append([z.AssociationGroupInformation,
                      z.AssociationGroupInformation_ListGet, 0, no])

        self.BatchCommandSubmitFilteredSlow(c, XMIT_OPTIONS)

    def AssociationAdd(self, group, n):
        reqs = [[z.Association, z.Association_Set, group, [n]],
                [z.Association, z.Association_Get, group]]
        self.BatchCommandSubmitFilteredFast(reqs, XMIT_OPTIONS)

    def AssociationRemove(self, group, n):
        reqs = [[z.Association, z.Association_Remove, group, [n]],
                [z.Association, z.Association_Get, group]]
        self.BatchCommandSubmitFilteredFast(reqs, XMIT_OPTIONS)

    def RefreshDynamicValues(self):
        logging.warning("[%d] RefreshDynamic", self.n)
        self.BatchCommandSubmitFilteredSlow(_DYNAMIC_PROPERTY_QUERIES,
                                            XMIT_OPTIONS)

        self.BatchCommandSubmitFilteredSlow(
            SensorMultiLevelQueries(self.sensors.Supported()),
            XMIT_OPTIONS)

        self.BatchCommandSubmitFilteredSlow(
            MeterQueries(self.meters.Supported()),
            XMIT_OPTIONS)

        self.BatchCommandSubmitFilteredSlow(
            ColorQueries(self.values.Get(KEY_COLOR_SWITCH_SUPPORTED).value),
            XMIT_OPTIONS)

    def RefreshStaticValues(self):
        logging.warning("[%d] RefreshStatic", self.n)
        self.BatchCommandSubmitFilteredSlow(_STATIC_PROPERTY_QUERIES, XMIT_OPTIONS)
        self.BatchCommandSubmitFilteredSlow(
            CommandVersionQueries(self.commands.Classes()),
            XMIT_OPTIONS)
        self.BatchCommandSubmitFilteredSlow(
            MultiInstanceSupportQueries(self.commands.Classes()),
            XMIT_OPTIONS)

        # This must be last as we use this as an indicator for the
        # NODE_STATE_INTERVIEWED
        last = (z.ManufacturerSpecific, z.ManufacturerSpecific_Get, {})
        self.BatchCommandSubmitFilteredSlow([last], XMIT_OPTIONS)

    def _MaybeChangeState(self, new_state):
        old_state = self._state
        if old_state < new_state:
            logging.warning(
                "[%d] state transition %s -- %s", self.n, old_state, new_state)
            self._state = new_state
        if new_state == actions.NODE_STATE_DISCOVERED:
            if old_state < new_state and self.commands.HasCommandClass(z.Security):
                pass
            # self._InitializeSecurity()
            elif old_state < actions.NODE_STATE_INTERVIEWED:
                self.RefreshStaticValues()
        else:
            self.RefreshDynamicValues()

    def put(self, _, key0, key1, values):
        if key0 is None:
            self._InitializeCommands(values["type"], values["commands"], values["controls"])
            self._MaybeChangeState(actions.NODE_STATE_DISCOVERED)
            return

        prefix = command.StringifyCommamnd(key0, key1)
        #logging.warning("@@@@@ %s: %s", prefix, values)

        if self._state < actions.NODE_STATE_DISCOVERED:
            self._protocol_node.Ping(3, False)

        new_state = actions.STATE_CHANGE.get((key0, key1))
        if new_state is not None:
            self._MaybeChangeState(new_state)

        func = actions.ACTIONS.get((key0, key1))
        if func is None:
            logging.error("%s unknown command", prefix)
            return

        func(self, key0, key1, values)

        # elif a == command.ACTION_STORE_MAP:
        #    val = command.GetValue(actions, value, prefix)
        #    if val.kind not in self._values:
        #        self._values[val.kind] = {}
        #    self._values[val.kind][val.unit] = val
        # elif a == command.ACTION_STORE_SCENE:
        #    if value[0] == 0:
        #        # TODO
        #        #self._values[command.VALUE_ACTIVE_SCENE] = -1
        #        pass
        #    else:
        #        self.scenes[value[0]] = value[1:]
        # elif a == command.SECURITY_SCHEME:
        #    assert len(value) == 1
        #    if value[0] == 0:
        #        # not paired yet start key exchange
        #        self.SecurityChangeKey(self._shared,security_key)
        #    else:
        #        # already paired
        #        self.SecurityRequestClasses()
        return


class ApplicationNodeSet(object):
    """NodeSet represents the collection of all nodes in a zwave network.

    All incoming application messages from the nodes (to the controller) are arrving in the
    message_queue (_shared.mq).

    The class spawns a receiver thread, which listens to incoming messages and dispatches them
    to the node obect they are coming to.

    It also spawns a refresher Thread that will occasionally prompt nodes
    that has not been active for a while to send update requests.

    Outgoing messages from the controller to the nodes are put in the message_queue directly
    by the individual node objects.

    """

    def __init__(self, nodeset: protocol_node.NodeSet):
        self._nodeset = nodeset
        self._nodes = {}

    def GetNode(self, n):
        node = self._nodes.get(n)
        if node is None:
            node = ApplicationNode(n, self._nodeset.GetNode(n))
            self._nodes[n] = node
        return node

    def put(self, n, ts, key0, key1, values):
        node = self.GetNode(n)
        node.put(ts, key0, key1, values)
