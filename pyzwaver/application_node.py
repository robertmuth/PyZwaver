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

from pyzwaver import zmessage
from pyzwaver import zwave as z
from pyzwaver import protocol_node
from pyzwaver import command
from pyzwaver import value


def Hexify(t):
    return ["%02x" % i for i in t]


NODE_STATE_NONE = "0_None"
NODE_STATE_INCLUDED = "1_Included"
# discovered means we have the command classes
NODE_STATE_DISCOVERED = "2_Discovered"
# interviewed means we have received product info (including most static
# info an versions)
NODE_STATE_INTERVIEWED = "3_Interviewed"


def _AssociationSubkey(v):
    return v["group"]


_COMMANDS_WITH_MAP_VALUES = {
    z.Version_CommandClassReport: lambda v: v["class"],
    z.Meter_Report: lambda v: (v["meter"]["type"], v["meter"]["unit"]),
    z.Configuration_Report: lambda v: v["parameter"],
    z.SensorMultilevel_Report: lambda v: (v["type"], v["value"]["unit"]),
    z.Association_Report: _AssociationSubkey,
    z.AssociationGroupInformation_NameReport: _AssociationSubkey,
    z.AssociationGroupInformation_InfoReport: _AssociationSubkey,
    z.AssociationGroupInformation_ListReport: _AssociationSubkey,
    z.UserCode_Report: lambda v: v["user"]
}

_COMMANDS_WITH_SPECIAL_ACTIONS = {
    z.ManufacturerSpecific_Report: lambda node, _: node._MaybeChangeState(NODE_STATE_INTERVIEWED),
}

XMIT_OPTIONS_NO_ROUTE = (z.TRANSMIT_OPTION_ACK |
                         z.TRANSMIT_OPTION_EXPLORE)

XMIT_OPTIONS = (z.TRANSMIT_OPTION_ACK |
                z.TRANSMIT_OPTION_AUTO_ROUTE |
                z.TRANSMIT_OPTION_EXPLORE)

XMIT_OPTIONS_SECURE = (z.TRANSMIT_OPTION_ACK |
                       z.TRANSMIT_OPTION_AUTO_ROUTE)

_DYNAMIC_PROPERTY_QUERIES = [
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


def SensorMultiLevelQueries(sensors):
    # older version
    return ([(z.SensorMultilevel_Get, {})] +
            [(z.SensorMultilevel_Get, {"sensor": s}) for s in sensors])


def DynamicPropertyQueriesMultiInstance(instances):
    out = []
    for i in instances:
        out.append((z.MultiInstance_Encap, {
            "mode": i,
            "command": list(z.SensorMultilevel_Get)}))
    return out


def MeterQueries(scales=(0, 1, 2, 3)):
    # older versions
    return ([(z.Meter_Get, {})] +
            # newer versions
            [(z.Meter_Get, {"scale": s << 3}) for s in scales])


_STATIC_PROPERTY_QUERIES = [
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
    (z.MultiInstance_ChannelEndPointGet, {}),

    # device type
    (z.ManufacturerSpecific_DeviceSpecificGet, {"type": 0}),
    # serial no
    (z.ManufacturerSpecific_DeviceSpecificGet, {"type": 1}),

    (z.TimeParameters_Get, {}),
    (z.ZwavePlusInfo_Get, {}),
    (z.SwitchAll_Get, {}),
    (z.Alarm_SupportedGet, {}),
    # mostly static
    # [zwave.AssociationCommandConfiguration, zwave.AssociationCommandConfiguration_SupportedGet],
    (z.NodeNaming_Get, {}),
    (z.NodeNaming_LocationGet, {}),
    (z.ColorSwitch_SupportedGet, {}),
    # arguably dynamic
    (z.Clock_Get, {}),
    (z.Firmware_MetadataGet, {}),
    (z.Association_GroupingsGet, {}),
]


def _ColorQueries(groups):
    return [(z.ColorSwitch_Get, {"group": g}) for g in groups]


def _CommandVersionQueries(classes):
    return [(z.Version_CommandClassGet, {"class": c}) for c in classes]


def _MultiInstanceSupportQueries(classes):
    return [(z.MultiInstance_Get, {"mode": c}) for c in classes]


def BitsToSetWithOffset(x, offset):
    out = set()
    pos = 0
    while x:
        if (x & 1) == 1:
            out.add(pos + offset)
        pos += 1
        x >>= 1
    return out


class NodeValues:

    def __init__(self):
        self._values = {}
        self._maps = {}

    def HasValue(self, key: tuple):
        return key in self._values

    def Set(self, ts, key: tuple, value):
        if value is None:
            return
        self._values[key] = ts, value

    def SetMapEntry(self, ts, key: tuple, subkey, value):
        if value is None:
            return
        m = self._maps.get(key)
        if m is None:
            m = {}
            self._maps[key] = m
        m[subkey] = ts, value

    def Get(self, key: tuple) -> map:
        v = self._values.get(key)
        if v is not None:
            return v[1]
        return None

    def GetMap(self, key: tuple) -> map:
        return self._maps.get(key, {})

    def ColorSwitchSupported(self):
        v = self.Get(z.ColorSwitch_SupportedReport)
        if not v:
            return set()
        # TODO - double check
        return BitsToSetWithOffset(v["bits"]["value"], 0)

    def SensorSupported(self):
        v = self.Get(z.SensorMultilevel_SupportedReport)
        if not v:
            return set()
        return BitsToSetWithOffset(v["bits"]["value"], 1)

    def MeterSupported(self):
        v = self.Get(z.Meter_SupportedReport)
        if not v:
            return set()
        return BitsToSetWithOffset(v["scale"], 0)

    def MeterFlags(self):
        v = self.Get(z.Meter_SupportedReport)
        if not v:
            return None
        return v["type"]

    def GetMultilevelSwitchLevel(self):
        v = self.Get(z.SwitchMultilevel_Report)
        if not v:
            return 0
        return v["level"]

    def ProductInfo(self):
        v = self.Get(z.ManufacturerSpecific_Report)
        if not v:
            return 0, 0, 0
        return v.get("manufacturer", 0), v.get("type", 0), v.get("product", 0)

    def ListAssociationGroupNumbers(self):
        m = self.GetMap(z.Association_Report)
        if m:
            return m.keys()
        v = self.Get(z.Association_GroupingsReport)
        if not v or v["count"] in [0, 255]:
            n = 4
        else:
            n = v["count"]
        return list(range(1, n + 1)) + [255]

    def HasCommandClass(self, cls):
        m = self.GetMap(z.Version_CommandClassReport)
        return cls in m

    def NumCommands(self):
        m = self.GetMap(z.Version_CommandClassReport)
        return len(m)

    def HasAlternaticeForBasicCommand(self):
        m = self.GetMap(z.Version_CommandClassReport)
        return z.SwitchBinary in m or z.SwitchMultilevel in m

    def Classes(self):
        m = self.GetMap(z.Version_CommandClassReport)
        return m.keys()

    def CommandVersions(self):
        m = self.GetMap(z.Version_CommandClassReport)
        return [(cls, command.StringifyCommandClass(cls), val["version"])
                for cls, (_, val) in m.items()
                if val["version"] != 0]

    def Configuration(self):
        m = self.GetMap(z.Configuration_Report)
        return [(no, val["value"]["size"], val["value"]["value"]) for no, (_, val) in m.items()]

    def Values(self):
        return [(key, command.StringifyCommand(key), val)
                for key, (_, val) in self._values.items()]

    def Sensors(self):
        m = self.GetMap(z.SensorMultilevel_Report)
        return [(key, value.GetSensorMeta(val), val)
                for key, (_, val) in m.items()]

    def Meters(self):
        m = self.GetMap(z.Meter_Report)
        return [(key, value.GetMeterMeta(val), val)
                for key, (_, val) in m.items()]

    def Associations(self):
        groups = self.GetMap(z.Association_Report)
        names = self.GetMap(z.AssociationGroupInformation_NameReport)
        infos = self.GetMap(z.AssociationGroupInformation_InfoReport)
        lists = self.GetMap(z.AssociationGroupInformation_ListReport)
        all = set(groups.keys())
        all |= infos.keys()
        all |= lists.keys()
        all |= names.keys()

        def foo(m, k):
            e = m.get(k)
            if e is None:
                return None
            return e[1]

        out = []
        for n in all:
            out.append((n, foo(groups, n), foo(names, n), foo(infos, n), foo(lists, n)))
        return out

    def Versions(self):
        v = self.Get(z.Version_Report)
        if not v:
            return 0, 0, 0, 0
        return v.get("library", 0), v.get("protocol", 0), v.get("firmware", 0), v.get("hardware", 0)

    def __str__(self):
        out = []
        out.append("  values:")
        for x in sorted(self.Values()):
            out.append("    " + str(x))
        out.append("  configuration:")
        for x in sorted(self.Configuration()):
            out.append("    " + str(x))
        out.append("  commands:")
        for x in sorted(self.CommandVersions()):
            out.append("    " + str(x))
        out.append("  associations:")
        for x in sorted(self.Associations()):
            out.append("    " + str(x))
        if self.MeterSupported():
            out.append("  meters:")
            for x in sorted(self.Meters()):
                out.append("    " + str(x))
        if self.SensorSupported():
            out.append("  sensors:")
            for x in sorted(self.Sensors()):
                out.append("    " + str(x))
        return "\n".join(out)


class ApplicationNode:
    """ApplicationNode represents a single node in a zwave network at the application level.

    Application level messages are passed to it via put()
    """

    def __init__(self, n, proto_node: protocol_node.Node):
        assert n >= 1
        self.n = n
        self.name = "Node %d" % n
        self.protocol_node = proto_node
        self.state = NODE_STATE_NONE
        self._controls = set()
        #
        self.values = NodeValues()
        self.scenes = {}

    def IsSelf(self):
        return self.protocol_node._is_controller

    def IsInterviewed(self):
        return self.state == NODE_STATE_INTERVIEWED

    def __lt__(self, other):
        return self.n < other.n

    def InitializeUnversioned(self, cmd, controls, std_cmd, std_controls):
        self._controls |= set(controls)
        self._controls |= set(std_controls)

        NO_VERSION = {"version": -1}
        ts = 0.0
        for k in cmd:
            if not self.values.HasCommandClass(k):
                self.values.SetMapEntry(ts, z.Version_CommandClassReport, k, NO_VERSION)
        for k in controls:
            if not self.values.HasCommandClass(k):
                self.values.SetMapEntry(ts, z.Version_CommandClassReport, k, NO_VERSION)
        for k in std_cmd:
            if not self.values.HasCommandClass(k):
                self.values.SetMapEntry(ts, z.Version_CommandClassReport, k, NO_VERSION)

        k = z.MultiInstance
        if k in self._controls:
            if not self.values.HasCommandClass(k):
                self.values.SetMapEntry(ts, z.Version_CommandClassReport, k, NO_VERSION)

    def BasicString(self):
        out = [
            "NODE: %d" % self.n,
            "state: %s" % self.state[2:],
            "version: %d:%d:%d:%d" % self.values.Versions(),
            "product: %04x:%04x:%04x" % self.values.ProductInfo(),
            "groups: %d" % len(self.values.ListAssociationGroupNumbers()),
        ]
        return "  ".join(out)

    def __str__(self):
        return self.BasicString() + "\n" + str(self.values)

    def BatchCommandSubmitFiltered(self, commands, priority: tuple, xmit: int):
        for c in commands:
            if len(c) != 2:
                logging.error("BAD COMMAND: %s", c)
                assert False

        for key, values in commands:
            if not self.values.HasCommandClass(key[0]):
                continue

            # if self._IsSecureCommand(cmd[0], cmd[1]):
            #    self._secure_messaging.Send(cmd)
            #    continue

            self.protocol_node.SendCommand(key, values, priority, xmit)

    def BatchCommandSubmitFilteredSlow(self, commands, xmit):
        self.BatchCommandSubmitFiltered(commands, zmessage.NodePriorityLo(self.n), xmit)

    def BatchCommandSubmitFilteredFast(self, commands, xmit):
        self.BatchCommandSubmitFiltered(commands, zmessage.NodePriorityHi(self.n), xmit)

    # def _IsSecureCommand(self, key0, key1):
    #    if key0 == z.Security:
    #        return key1 in [z.Security_NetworkKeySet, z.Security_SupportedGet]
    #
    #   return self._secure_commands.HasCommandClass(key0)

    def _InitializeSecurity(self):
        logging.error("[%d] initializing security", self.n)
        # self.RefreshStaticValues()
        self.BatchCommandSubmitFilteredSlow(
            [(z.Security_SchemeGet, 0)], XMIT_OPTIONS)

    def _InitializeCommands(self, typ, cmd, controls):
        k = typ[1] * 256 + typ[2]
        v = z.GENERIC_SPECIFIC_DB.get(k)
        if v is None:
            logging.error("[%d] unknown generic device : ${type}", self.n)
            return
        self.InitializeUnversioned(cmd, controls, v[1], v[2])

    def ProbeNode(self):
        self.BatchCommandSubmitFilteredFast(
            [(z.NoOperation_Set, {})],
            XMIT_OPTIONS)

    #        cmd = zwave_cmd.MakeWakeUpIntervalCapabilitiesGet(
    #            self.n, xmit, driver.GetCallbackId())
    #        driver.Send(cmd, handler, "WakeUpIntervalCapabilitiesGet")

    def RefreshCommandVersions(self, classes):
        self.BatchCommandSubmitFilteredSlow(_CommandVersionQueries(classes),
                                            XMIT_OPTIONS)

    def RefreshAllCommandVersions(self):
        self.RefreshCommandVersions(range(255))

    def RefreshSceneActuatorConfigurations(self, scenes):
        c = [(z.SceneActuatorConf_Get, {"group": s}) for s in scenes]
        self.BatchCommandSubmitFilteredSlow(c, XMIT_OPTIONS)

    def RefreshAllParameters(self):
        c = [(z.Configuration_Get, {"parameter": p})
             for p in range(255)]
        self.BatchCommandSubmitFilteredSlow(c, XMIT_OPTIONS)

    def SetConfigValue(self, param, size, value, request_update=True):
        c = [(z.Configuration_Set, param, {size, value})]
        if request_update:
            c += [(z.Configuration, z.Configuration_Get, {param})]
        self.BatchCommandSubmitFilteredFast(c, XMIT_OPTIONS)

    def SetSceneConfig(self, scene, delay, extra, level, request_update=True):
        self.BatchCommandSubmitFilteredFast(
            [(z.SceneActuatorConf_Set,
              {scene, delay, extra, level})], XMIT_OPTIONS)
        if not request_update:
            return
        self.BatchCommandSubmitFilteredFast(
            [(z.SceneActuatorConf, z.SceneActuatorConf_Get, {scene})], XMIT_OPTIONS)

    def ResetMeter(self, request_update=True):
        # TODO
        c = [(z.Meter_Reset, {})]
        # if not request_update:
        #    c += [(z.Meter_Get, {})]
        self.BatchCommandSubmitFilteredFast(c, XMIT_OPTIONS)

    def SetBasic(self, value, request_update=True):
        c = [(z.Basic_Set, {"level": value})]
        if request_update:
            c += [(z.Basic_Get, {})]
        self.BatchCommandSubmitFilteredFast(c, XMIT_OPTIONS)

    # Version 1 of the command class does not support `delay`
    def SetMultilevelSwitch(self, value, delay=0, request_update=True):
        c = [(z.SwitchMultilevel_Set, {"level": value, "duration": delay})]
        if request_update:
            c += [(z.SwitchBinary_Get, {}),
                  (z.SwitchMultilevel_Get, {})]
        self.BatchCommandSubmitFilteredFast(c, XMIT_OPTIONS)

    def SetBinarySwitch(self, value, request_update=True):
        c = [(z.SwitchBinary_Set, {value})]
        if request_update:
            c += [(z.SwitchBinary_Get, {}),
                  (z.SwitchMultilevel_Get, {})]
        self.BatchCommandSubmitFilteredFast(c, XMIT_OPTIONS)

    def RefreshAssociations(self):
        c = []
        for no in self.values.ListAssociationGroupNumbers():
            v = {"group": no}
            c.append((z.Association_Get, v))
            c.append((z.AssociationGroupInformation_NameGet, v))
            v = {"group": no, "mode": 0}
            c.append((z.AssociationGroupInformation_ListGet, v))
            c.append((z.AssociationGroupInformation_InfoGet, v))
        self.BatchCommandSubmitFilteredSlow(c, XMIT_OPTIONS)

    def AssociationAdd(self, group, n):
        # TODO
        c = [(z.Association_Set, group, [n]),
             (z.Association_Get, group)]
        self.BatchCommandSubmitFilteredFast(c, XMIT_OPTIONS)

    def AssociationRemove(self, group, n):
        # TODO: broken
        c = [(z.Association_Remove, {group, n}),
             (z.Association_Get, {group})]
        self.BatchCommandSubmitFilteredFast(c, XMIT_OPTIONS)

    def RefreshDynamicValues(self):
        logging.warning("[%d] RefreshDynamic", self.n)
        c = (_DYNAMIC_PROPERTY_QUERIES +
             SensorMultiLevelQueries(self.values.SensorSupported()) +
             MeterQueries(self.values.MeterSupported()) +
             _ColorQueries(self.values.ColorSwitchSupported()))
        self.BatchCommandSubmitFilteredSlow(c, XMIT_OPTIONS)

    def RefreshStaticValues(self):
        logging.warning("[%d] RefreshStatic", self.n)
        self.BatchCommandSubmitFilteredSlow(_STATIC_PROPERTY_QUERIES, XMIT_OPTIONS)
        self.BatchCommandSubmitFilteredSlow(
            _CommandVersionQueries(self.values.Classes()),
            XMIT_OPTIONS)
        self.BatchCommandSubmitFilteredSlow(
            _MultiInstanceSupportQueries(self.values.Classes()),
            XMIT_OPTIONS)

        # This must be last as we use this as an indicator for the
        # NODE_STATE_INTERVIEWED
        last = (z.ManufacturerSpecific_Get, {})
        self.BatchCommandSubmitFilteredSlow([last], XMIT_OPTIONS)

    def _MaybeChangeState(self, new_state):
        old_state = self.state
        if old_state < new_state:
            logging.warning(
                "[%d] state transition %s -- %s", self.n, old_state, new_state)
            self.state = new_state
        if new_state == NODE_STATE_DISCOVERED:
            if old_state < new_state and self.values.HasCommandClass(z.Security):
                pass
            # self._InitializeSecurity()
            elif old_state < NODE_STATE_INTERVIEWED:
                self.RefreshStaticValues()
        else:
            self.RefreshDynamicValues()

    def put(self, ts, key, values):

        if key[0] is None:
            self._InitializeCommands(values["type"], values["commands"], values["controls"])
            self._MaybeChangeState(NODE_STATE_DISCOVERED)
            return

        if self.state < NODE_STATE_DISCOVERED:
            self.protocol_node.Ping(3, False)

        special = _COMMANDS_WITH_SPECIAL_ACTIONS.get(key)
        if special:
            special(self, values)

        key_ex = _COMMANDS_WITH_MAP_VALUES.get(key)
        if key_ex:
            self.values.SetMapEntry(ts, key, key_ex(values), values)
        else:
            self.values.Set(ts, key, values)

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
        self.nodes = {}

    def GetNode(self, n):
        node = self.nodes.get(n)
        if node is None:
            node = ApplicationNode(n, self._nodeset.GetNode(n))
            self.nodes[n] = node
        return node

    def put(self, n, ts, key, values):
        node = self.GetNode(n)
        node.put(ts, key, values)
