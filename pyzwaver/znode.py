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
import random
import struct
import sys
import threading
import time
import traceback
import queue

from pyzwaver import zmessage
from pyzwaver import command
from pyzwaver import zwave


def Hexify(t):
    return ["%02x" % i for i in t]

XMIT_OPTIONS_NO_ROUTE = (zwave.TRANSMIT_OPTION_ACK |
                         zwave.TRANSMIT_OPTION_EXPLORE)

XMIT_OPTIONS = (zwave.TRANSMIT_OPTION_ACK |
                zwave.TRANSMIT_OPTION_AUTO_ROUTE |
                zwave.TRANSMIT_OPTION_EXPLORE)

XMIT_OPTIONS_SECURE = (zwave.TRANSMIT_OPTION_ACK |
                       zwave.TRANSMIT_OPTION_AUTO_ROUTE)


_DYNAMIC_PROPERTY_QUERIES = [
    # Basic should be first
    [zwave.Basic, zwave.Basic_Get],
    [zwave.Alarm, zwave.Alarm_Get],
    [zwave.SensorBinary, zwave.SensorBinary_Get],
    [zwave.Battery, zwave.Battery_Get],

    [zwave.Lock, zwave.Lock_Get],
    [zwave.DoorLock, zwave.DoorLock_Get],

    [zwave.Powerlevel, zwave.Powerlevel_Get],
    [zwave.Protection, zwave.Protection_Get],
    #[zwave.SensorBinary, zwave.SensorBinary_Get],
    [zwave.SwitchBinary, zwave.SwitchBinary_Get],
    [zwave.SwitchMultilevel, zwave.SwitchMultilevel_Get],
    [zwave.SwitchToggleBinary, zwave.SwitchToggleBinary_Get],
    # only v5 offer the extra parameter
    [zwave.Indicator, zwave.Indicator_Get],
    # get the current scene
    [zwave.SceneActuatorConf, zwave.SceneActuatorConf_Get, 0],
    [zwave.SensorAlarm, zwave.SensorAlarm_Get],
    [zwave.ThermostatMode, zwave.ThermostatMode_Get]
]


def SensorMultiLevelQueries(sensors):
    # older version
    return ([[zwave.SensorMultilevel, zwave.SensorMultilevel_Get, None]] +
            [[zwave.SensorMultilevel, zwave.SensorMultilevel_Get, s] for s in sensors])


def DynamicPropertyQueriesMultiInstance(instances):
    out = []
    for i in instances:
        out.append([zwave.MultiInstance, zwave.MultiInstance_Encap, i,
                    zwave.SensorMultilevel, zwave.SensorMultilevel_Get])
    return out


def MeterQueries(scales=(0, 1, 2, 3)):
    # older versions
    return ([[zwave.Meter, zwave.Meter_Get, None]] +
            # newer versions
            [[zwave.Meter, zwave.Meter_Get, s << 3] for s in scales])

_STATIC_PROPERTY_QUERIES = [
    [zwave.SensorMultilevel, zwave.SensorMultilevel_SupportedGet],

    [zwave.UserCode, zwave.UserCode_NumberGet],
    [zwave.DoorLock, zwave.DoorLock_ConfigurationGet],
    [zwave.DoorLockLogging, zwave.DoorLockLogging_SupportedGet],

    [zwave.Association, zwave.Association_GroupingsGet],
    [zwave.Meter, zwave.Meter_SupportedGet],
    [zwave.SensorAlarm, zwave.SensorAlarm_SupportedGet],
    [zwave.ThermostatMode, zwave.ThermostatMode_SupportedGet],
    [zwave.ThermostatSetpoint, zwave.ThermostatSetpoint_SupportedGet],
    [zwave.Version, zwave.Version_Get],
    [zwave.SwitchMultilevel, zwave.SwitchMultilevel_SupportedGet],
    [zwave.MultiInstance, zwave.MultiInstance_ChannelEndPointGet],

    [zwave.ManufacturerSpecific,
        zwave.ManufacturerSpecific_DeviceSpecificGet, 0],

    [zwave.TimeParameters, zwave.TimeParameters_Get],
    [zwave.ZwavePlusInfo, zwave.ZwavePlusInfo_Get],
    [zwave.SwitchAll, zwave.SwitchAll_Get],
    [zwave.Alarm, zwave.Alarm_SupportedGet],
    # mostly static
    #[zwave.AssociationCommandConfiguration, zwave.AssociationCommandConfiguration_SupportedGet],
    [zwave.NodeNaming, zwave.NodeNaming_Get],
    [zwave.NodeNaming, zwave.NodeNaming_LocationGet],
    [zwave.ColorSwitch, zwave.ColorSwitch_SupportedGet],
    # arguably dynamic
    [zwave.Clock, zwave.Clock_Get],
    [zwave.Firmware, zwave.Firmware_MetadataGet],
]


def CommandVersionQueries(classes):
    return [[zwave.Version, zwave.Version_CommandClassGet, c] for c in classes]


def MultiInstanceSupportQueries(classes):
    return [[zwave.MultiInstance, zwave.MultiInstance_Get, c] for c in classes]


_BAUD = [
    "unknown_baud",
    "9600_baud",
    "40000_baud",
    "100000_baud",
    "unknown_baud",
    "unknown_baud",
    "unknown_baud",
    "unknown_baud",
]


def BitsToSetWithOffset(x, offset):
    out = set()
    pos = 0
    while x:
        if (x & 1) == 1:
            out.add(pos + offset)
        pos += 1
        x >>= 1
    return out


# SensorMultilevel_Report rewrites for buggy AeonLabs sensor labs firmware.
#  01 3a 01 15
#  01 3a 01 0d
#  01 3a 00 f9
#  01 32 01 25
#  01 32 00 f4

def MaybePatchCommand(m):
    if m[0] == zwave.MultiInstance and m[1] == zwave.MultiInstance_Encap:
        logging.warning("received MultiInstance_Encap for instance")
        return m[4:]

    if (m[0] == zwave.SensorMultilevel and
        m[1] == zwave.SensorMultilevel_Report and
        m[2] == 1 and
            ((m[3] & 7) > len(m) - 4)):
        x = 1 << 5 | (0 << 3) | 2
        # [49, 5, 1, 127, 1, 10] => [49, 5, 1, X, 1, 10]
        logging.warning(
            "fixing up SensorMultilevel_Report %s: [3] %02x-> %02x", Hexify(m), m[3], x)
        m[3] = x
    if (m[0] == zwave.SensorMultilevel and
        m[1] == zwave.SensorMultilevel_Report and
        m[2] == 1 and
            (m[3] & 0x10) != 0):
        x = m[3] & 0xe7
        logging.warning(
            "fixing up SensorMultilevel_Report %s: [3] %02x-> %02x", Hexify(m), m[3], x)
        m[3] = x
    return m


DEFAULT_PRODUCT = [0, 0, 0]


def RenderValues(values):
    return str([str(v) for v in sorted(values)])

def CompactifyParams(params):
    out = []
    last = [-1, -1, -1,-1]  # range start, range end, size, value
    for k in sorted(params.keys()):
        a, b = params[k]
        if last[2] != a or last[3] != b or last[1] != k - 1:
            last = [k, k, a, b]
            out.append(last)
        else:
            last[1] = k  # increment range end
    return out

_DEFAULT_PRODUCT = command.Value(
    command.VALUE_MANFACTURER_SPECIFIC, command.UNIT_NONE, [0, 0, 0])

_DEFAULT_VERSION = command.Value(
    command.VALUE_VERSION, command.UNIT_NONE, [-1, 0, 0, 0, 0])

_DEFAULT_METER_SUPPORTED = command.Value(
    command.VALUE_METER_SUPPORTED, command.UNIT_NONE, [0, 0])

_DEFAULT_SENSOR_SUPPORTED = command.Value(
    command.VALUE_SENSOR_SUPPORTED, command.UNIT_NONE, 0)

_DEFAULT_VALUE_ASSOCIATIONS = command.Value(
    command.VALUE_ASSOCIATIONS, command.UNIT_NONE, 0)

_DEFAULT_MULTILEVEL_SWITCH_SENSOR = command.Value(
    command.SENSOR_KIND_SWITCH_MULTILEVEL, command.UNIT_LEVEL, 0)

_DEFAULT_MULTILEVEL_SWITCH_SENSOR = command.Value(
    command.SENSOR_KIND_SWITCH_MULTILEVEL, command.UNIT_LEVEL, 0)

class Node:

    """Node represents a single node in a zwave network.

    The message_queue (_mq) is used to send messages to the node.
    Message from the node are  ProcessCommand()
    """

    def __init__(self, n, message_queue, event_cb):
        assert n >= 1
        self._mq = message_queue
        self.n = n
        self._failed = True
        self._is_self = False      # node is the controller
        self._state = command.NODE_STATE_NONE
        self._last_contact = 0.0
        #
        self.device_description = ""
        self.device_type = (0, 0, 0)
        self._protocol_version = 0

        self._commands = {}
        self._controls = set()

        self._values = {}
        self._events = {}
        self._meters = {}
        self._sensors = {}
        self._parameters = {}
        self._associations = {}
        #
        self.scenes = {}
        self._event_cb = event_cb
        #
        self.flags = set()
        # static config

        # semi static

        # values:
        self.awake = True
        self._security_queue = queue.Queue()

    def IsSelf(self):
        return self._is_self

    def ProductInfo(self):
        p = self._values.get(
            command.VALUE_MANFACTURER_SPECIFIC, _DEFAULT_PRODUCT)
        return tuple(p.value)

    def LibraryType(self):
        p = self._values.get(command.VALUE_VERSION, _DEFAULT_VERSION)
        return p.value[0]

    def SDKVersion(self):
        p = self._values.get(command.VALUE_VERSION, _DEFAULT_VERSION)
        return (p.value[1], p.value[2])

    def ApplicationVersion(self):
        p = self._values.get(command.VALUE_VERSION, _DEFAULT_VERSION)
        return (p.value[3], p.value[4])

    def MeterType(self):
        p = self._values.get(command.VALUE_METER_SUPPORTED, _DEFAULT_METER_SUPPORTED)
        return p.value[0] & 0x1f

    def GetMultilevelSwitchLevel(self):
        k = (command.SENSOR_KIND_SWITCH_MULTILEVEL, command.UNIT_LEVEL)
        p = self._sensors.get(k, _DEFAULT_MULTILEVEL_SWITCH_SENSOR)
        return p.value

    def MeterResetable(self):
        p = self._values.get(command.VALUE_METER_SUPPORTED, _DEFAULT_METER_SUPPORTED)
        return (p.value[0] & 0x80) != 0

    def MeterSupported(self):
        p = self._values.get(command.VALUE_METER_SUPPORTED, _DEFAULT_METER_SUPPORTED)
        return BitsToSetWithOffset(p.value[1], 0)

    def SensorSupported(self):
        p = self._values.get(command.VALUE_SENSOR_SUPPORTED, _DEFAULT_SENSOR_SUPPORTED)
        return BitsToSetWithOffset(p.value, 1)

    def GetAllAssociations(self):
        return self._associations

    def GetAllSensors(self):
        return self._sensors.values()

    def GetAllMeters(self):
        return self._meters.values()

    def GetAllParameters(self):
        return self._parameters

    def GetAllCommandClasses(self):
        return self._commands

    def GetAllValues(self):
        return self._values

    def __lt__(self, other):
        return self.n < other.n

    def BasicString(self):
        out = [
            "NODE: %d" % self.n,
            "state: %s" % self._state,
            "last: %s" % self.RenderLastContact(),
            "protocol_version: %d" % self._protocol_version,
            "lib_type: %s" % self.LibraryType(),
            "sdk_version: %d:%d" % self.SDKVersion(),
            "app_version: %d:%d" % self.ApplicationVersion(),
            "\ndevice: %d:%d:%d" % self.device_type,
            "(%s)" % self.device_description,
            "product: %04x:%04x:%04x" % self.ProductInfo(),
            "\nflags:        " + repr(self.flags),
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
        if self.MeterSupported() or self._meters:
            out.append("  meters supp.: " +
                       command.RenderMeterList(
                           self.MeterType(), self.MeterSupported()))
            out.append(
                "  meters:       " + RenderValues(self._meters.values()))
        if self.SensorSupported() or self._sensors:
            out.append("  sensors supp.:" +
                       command.RenderSensorList(self.SensorSupported()))
            out.append(
                "  sensors:      " + RenderValues(self._sensors.values()))
        out.append("  values:       " + RenderValues(self._values.values()))
        out.append("  events:       " + repr(self._events))
        out.append("  associations: " + repr(self._associations))
        out.append("  parameters:   " + repr(CompactifyParams(self._parameters)))
        out.append("  commands:     " +
                   repr([(zwave.CMD_TO_STRING.get(c, "UKNOWN:%d" % c), c, v)
                        for c, v in self._commands.items()]))
        return "\n".join(out)

    def BasicInfo(self):
        return {
            "#": self.n,
            "state": self._state[2:],
            "device":  "%02d:%02d:%02d" % self.device_type,
            "product": "0x%04x:0x%04x:0x%04x  " % self.ProductInfo() + self.device_description,
            "sdk_version": "%d:%d" % self.SDKVersion(),
            "app_version":  "%d:%d" % self.ApplicationVersion(),
            "last_contact": self.RenderLastContact(),
            "lib_type": self.LibraryType(),
            "protocol_version": self._protocol_version
        }

    def HasAlternaticeForBasicCommand(self):
        return (zwave.SwitchBinary in self._commands or
                zwave.SwitchMultilevel in self._commands)

    def RenderLastContact(self):
        if self._last_contact == 0.0:
            return "never"
        d = time.time() - self._last_contact
        if d < 120.0:
            return "%d sec ago" % int(d)
        return "%d min ago" % (int(d) // 60)


    def SetValue(self, key, value):
        self._values[key] = (time.time(), value)

    def GetValue(self, key, default=None):
        v = self._values.get(key, [None, default])
        return v[1]

    def HasValue(self, key):
        return key in self._values

    def IsIntialized(self):
        """at the very least we should have received a ProcessUpdate(),
        ProcessProtocolInfo()
        """
        return self.device_type[0] != 0 and self._commands

    def HasCommandClass(self, cls):
        return cls in self._commands

    def _MaybeChangeState(self, new_state):
        old_state = self._state
        if old_state < new_state:
            logging.warning(
                "[%d] state transition %s -- %s", self.n, old_state, new_state)
            self._state = new_state
            self._event_cb(self.n, command.EVENT_STATE_CHANGE)
        if new_state == command.NODE_STATE_DISCOVERED:
            if old_state < new_state and self.HasCommandClass(zwave.Security):
                self._InitializeSecurity()
            elif old_state < command.NODE_STATE_INTERVIEWED:
                self.RefreshStaticValues()
        else:
            self.RefreshDynamicValues()


    def _InitializeSecurity(self):
        logging.error("[%d] initializing security", self.n)
        # self.RefreshStaticValues()
        self.BatchCommandSubmitFilteredSlow(
            [[zwave.Security, zwave.Security_SchemeGet, 0]], XMIT_OPTIONS)

    def InitializeExternally(self, product, library_type, is_self):
        self._is_self = is_self
        self._MaybeChangeState(command.NODE_STATE_INTERVIEWED)
        self.device_description = "THIS PC CONTROLLER"
        self.product = product
        self.library_type = library_type

    def _SetDeviceType(self, device_type):
        self.device_type = device_type
        k = device_type[1] * 256 + device_type[2]
        v = zwave.GENERIC_SPECIFIC_DB.get(k)
        if v is None:
            logging.error(
                "[%d] unknown generic device : %s", self.n, device_type)
            self.device_description = "unknown device_description: %s" % (
                device_type,)
        else:
            self.device_description = v[0]

        # self.UpdateIsFailedNode();

    def _InitializeCommands(self, typ, cmd, cntrl):
        k = typ[1] * 256 + typ[2]
        v = zwave.GENERIC_SPECIFIC_DB.get(k)
        if v is None:
            logging.error("[%d] unknown generic device : ${type}", self.n)
            return

        for k in cmd:
            if k not in self._commands:
                self._commands[k] = -1
        for k in v[1]:
            if k not in self._commands:
                self._commands[k] = -1

        self._controls |= set(cntrl)
        self._controls |= set(v[2])
        k = zwave.MultiInstance
        if k in self._controls and k not in self._commands:
            self._commands[k] = -1

    def ProcessNodeInfo(self, m):
        self._event_cb(self.n, command.EVENT_NODE_INFO)
        self._last_contact = time.time()
        m = MaybePatchCommand(m)
        logging.warning("[%d] process node info: %s", self.n, Hexify(m))
        cmd = []
        cntrl = []
        seen_marker = False
        for i in m[3:]:
            if i == zwave.Mark:
                seen_marker = True
            elif seen_marker:
                cntrl.append(i)
            else:
                cmd.append(i)

        typ = (m[0], m[1], m[2])
        self._SetDeviceType(typ)
        self._InitializeCommands(typ, cmd, cntrl)
        self._MaybeChangeState(command.NODE_STATE_DISCOVERED)

    def SecurityRequestClasses(self):
        pass

    def SecurityChangeKey(self, key):
        assert len(key) == 16

    def StoreValue(self, val):
        self._values[val.kind] = val
        self._event_cb(self.n, command.EVENT_VALUE_CHANGE)

    def StoreSensor(self, val):
        self._sensors[(val.kind, val.unit)] = val
        self._event_cb(self.n, command.EVENT_VALUE_CHANGE)

    def StoreMeter(self, val):
        self._meters[(val.kind, val.unit)] = val
        self._event_cb(self.n, command.EVENT_VALUE_CHANGE)

    def StoreCommandVersion(self, val):
        self._commands[val[0]] = val[1]
        self._event_cb(self.n, command.EVENT_VALUE_CHANGE)

    def StoreParameter(self, val):
        print ("@@@@@@@@@@@", val)
        self._parameters[val[0]] = val[1]
        self._event_cb(self.n, command.EVENT_VALUE_CHANGE)

    def StoreEvent(self, val):
        self._events[val.kind] = val
        self._event_cb(self.n, val.kind)

    def StoreAssociation(self, val):
        # we do not support extra long lists
        assert val[2] == 0
        self._associations[val[0]] = val[1:]
        self._event_cb(self.n, command.EVENT_VALUE_CHANGE)

    def _OneAction(self, a, actions, value):
        logging.info(
            "[%d]  action: %s (%s) value: %s", self.n, a, actions, value)
        if a == command.ACTION_STORE_COMMAND_VERSION:
            assert len(value) == 2
            if value[1] != 0:
                self.StoreCommandVersion(value)
        elif a == command.ACTION_STORE_SENSOR:
            self.StoreSensor(command.GetValue(actions, value))
        elif a == command.ACTION_STORE_VALUE:
            self.StoreValue(command.GetValue(actions, value))
        elif a == command.ACTION_STORE_MAP:
            val = command.GetValue(actions, value)
            if val.kind not in self._values:
                self._values[val.kind] = {}
            self._values[val.kind][val.unit] = val
        elif a == command.ACTION_STORE_EVENT:
            self.StoreEvent(command.GetValue(actions, value))
        elif a == command.ACTION_STORE_METER:
            self.StoreMeter(command.GetValue(actions, value))
        elif a == command.ACTION_STORE_PARAMETER:
            assert len(value) == 2
            self.StoreParameter(value)
        elif a == command.ACTION_STORE_SCENE:
            if value[0] == 0:
                # TODO
                #self._values[command.VALUE_ACTIVE_SCENE] = -1
                pass
            else:
                self.scenes[value[0]] = value[1:]
        elif a == command.ACTION_STORE_ASSOCIATION:
            assert len(value) == 4
            self.StoreAssociation(value)
        elif a == command.ACTION_CHANGE_STATE:
            state = actions.pop(0)
            self._MaybeChangeState(state)
        elif a == command.SECURITY_SCHEME:
            assert len(value) == 1
            if value[0] == 0:
                self.SecurityChangeKey([1] * 16)
            else:
                self.SecurityRequestClasses()
        else:
            logging.error("unexpected: %s %s %s", a, actions, value)
            assert False

    def ProcessCommand(self, data):
        self._last_contact = time.time()
        value = command.ParseCommand(data)
        k = (data[0], data[1])
        actions = command.ACTIONS.get(k)[:]
        if actions is None:
            logging.error("[%d] unknown command %s", self.n, Hexify(data))
            return
        while actions:
            a = actions.pop(0)
            self._OneAction(a, actions, value)

    def _ProcessProtocolInfo(self, m):
        flags = self.flags
        a, b, _, basic, generic, specific = struct.unpack(">BBBBBB", m)
        self._SetDeviceType((basic, generic, specific))
        if a & 0x80:
            flags.add("listening")
        if a & 0x40:
            flags.add("routing")
        baud = (a & 0x38) >> 3
        flags.add(_BAUD[baud])
        self._protocol_version = 1 + (a & 0x7)
        if b & 0x01:
            flags.add("security")
        if b & 0x02:
            flags.add("controller")
        if b & 0x04:
            flags.add("specific_device")
        if b & 0x08:
            flags.add("routing_slave")
        if b & 0x10:
            flags.add("beam_capable")
        if b & 0x20:
            flags.add("sensor_250ms")
        if b & 0x40:
            flags.add("sensor_1000ms")
        if b & 0x80:
            flags.add("optional_functionality")

    # Equivalent to controller function:
    def GetNodeProtocolInfo(self):
        def handler(message):
            if not message:
                logging.error("ProtocolInfo failed")
                return
            payload = message[4:-1]
            if len(payload) < 5:
                logging.error("bad ProtocolInfo payload: %s", message)
                return
            self._ProcessProtocolInfo(payload)

        logging.warn("[%d] GetNodeProtocolInfo", self.n)
        self.SendCommand(
            zwave.API_ZW_GET_NODE_PROTOCOL_INFO, [self.n], handler)

    def _RequestNodeInfo(self, retries):
        r = retries - 1

        def handler(m):
            if m[4] != 0:
                return  # success
            logging.warning("[%d] RequestNodeInfo failed: %s",
                            self.n, zmessage.PrettifyRawMessage(m))
            self._RequestNodeInfo(r)

        if retries > 0:
            logging.warning("[%d] RequestNodeInfo %d", self.n, retries)
            self.SendCommand(zwave.API_ZW_REQUEST_NODE_INFO, [self.n], handler)
        else:
            logging.error("[%d] RequestNodeInfo failed permanently", self.n)

    def _UpdateIsFailedNode(self, cb):
        if self._is_self:
            logging.warning("[%d] skip failed check for self", self.n)
            return

        def handler(m):
            self._failed = m[4] != 0
            if cb:
                cb(m)
        self.SendCommand(zwave.API_ZW_IS_FAILED_NODE_ID, [self.n], handler)

    def Ping(self, retries, force):
        logging.warning("[%d] Ping retries %d, force: %s", self.n, retries,
                        force)
        if self._is_self:
            logging.warning("[%d] ignore RequestNodeInfo for self", self.n)
            return

        self.GetNodeProtocolInfo()
        if force:
            self._UpdateIsFailedNode(None)
            self._RequestNodeInfo(retries)
        else:
            def handler(m):
                if not self._failed:
                    self._RequestNodeInfo(retries)
            self._UpdateIsFailedNode(handler)

    def ProbeNode(self):
        self.BatchCommandSubmitFilteredFast(
            [[zwave.NoOperation, zwave.NoOperation_Set]],
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
        c = [[zwave.SceneActuatorConf, zwave.SceneActuatorConf_Get, s]
             for s in scenes]
        self.BatchCommandSubmitFilteredSlow(c, XMIT_OPTIONS)

    def RefreshAllParameters(self):
        c = [[zwave.Configuration, zwave.Configuration_Get, p]
             for p in range(255)]
        self.BatchCommandSubmitFilteredSlow(c, XMIT_OPTIONS)

    def SetConfigValue(self, param, size, value, request_update=True):
        reqs = [[zwave.Configuration, zwave.Configuration_Set, param, (size, value)]]
        if request_update:
            reqs += [[zwave.Configuration, zwave.Configuration_Get, param]]
        self.BatchCommandSubmitFilteredFast(reqs, XMIT_OPTIONS)

    def SetSceneConfig(self, scene, delay, extra, level, request_update=True):
        self.BatchCommandSubmitFilteredFast(
            [[zwave.SceneActuatorConf, zwave.SceneActuatorConf_Set,
              scene, delay, extra, level]], XMIT_OPTIONS)
        if not request_update:
            return
        self.BatchCommandSubmitFilteredFast(
            [[zwave.SceneActuatorConf, zwave.SceneActuatorConf_Get, scene]], XMIT_OPTIONS)


    def ResetMeter(self, request_update=True):
        self.BatchCommandSubmitFilteredFast(
            [[zwave.Meter, zwave.Meter_Reset]], XMIT_OPTIONS)

    def SetBasic(self, value, request_update=True):
        self.BatchCommandSubmitFilteredFast(
            [[zwave.Basic, zwave.Basic_Set, value]],
            XMIT_OPTIONS)
        if not request_update:
            return
        reqs = [[zwave.Basic, zwave.Basic_Get]]
        self.BatchCommandSubmitFilteredFast(reqs, XMIT_OPTIONS)

    # Version 1 of the command class does not support `delay`
    def SetMultilevelSwitch(self, value, delay=0, request_update=True):
        reqs = [[zwave.SwitchMultilevel, zwave.SwitchMultilevel_Set, value, delay]]
        if request_update:
            reqs += [[zwave.SwitchBinary, zwave.SwitchBinary_Get],
                     [zwave.SwitchMultilevel, zwave.SwitchMultilevel_Get]]
        self.BatchCommandSubmitFilteredFast(reqs, XMIT_OPTIONS)

    def SetBinarySwitch(self, value, request_update=True):
        reqs = [[zwave.SwitchBinary, zwave.SwitchBinary_Set, value]]
        if request_update:
            reqs += [[zwave.SwitchBinary, zwave.SwitchBinary_Get],
                     [zwave.SwitchMultilevel, zwave.SwitchMultilevel_Get]]
        self.BatchCommandSubmitFilteredFast(reqs, XMIT_OPTIONS)

    def RefreshAssociations(self):
        n = self._values.get(command.VALUE_ASSOCIATIONS, _DEFAULT_VALUE_ASSOCIATIONS).value
        # work around for cooper stuff
        if n == 0 or n == 255:
            n = 4
        # 255 needed for cooper and wt00z
        groups = list(range(1, n + 1)) + [255]
        c = [[zwave.Association, zwave.Association_Get, g] for g in groups]
        self.BatchCommandSubmitFilteredSlow(c, XMIT_OPTIONS)

    def AssociationAdd(self, group, n):
        reqs = [[zwave.Association, zwave.Association_Set, group, [n]],
                [zwave.Association, zwave.Association_Get, group]]
        self.BatchCommandSubmitFilteredFast(reqs, XMIT_OPTIONS)

    def AssociationRemove(self, group, n):
        reqs = [[zwave.Association, zwave.Association_Remove, group, [n]],
                [zwave.Association, zwave.Association_Get, group]]
        self.BatchCommandSubmitFilteredFast(reqs, XMIT_OPTIONS)

    def RefreshDynamicValues(self):
        logging.warning("[%d] RefreshDynamic", self.n)
        self.BatchCommandSubmitFilteredSlow(_DYNAMIC_PROPERTY_QUERIES,
                                            XMIT_OPTIONS)
        self.BatchCommandSubmitFilteredSlow(
            SensorMultiLevelQueries(self.SensorSupported()),
            XMIT_OPTIONS)
        self.BatchCommandSubmitFilteredSlow(
            MeterQueries(self.MeterSupported()),
            XMIT_OPTIONS)

    def RefreshStaticValues(self):
        logging.warning("[%d] RefreshStatic", self.n)
        self.BatchCommandSubmitFilteredSlow(
            _STATIC_PROPERTY_QUERIES,
            XMIT_OPTIONS)
        self.BatchCommandSubmitFilteredSlow(
            CommandVersionQueries(self._commands),
            XMIT_OPTIONS)
        self.BatchCommandSubmitFilteredSlow(
            MultiInstanceSupportQueries(self._commands),
            XMIT_OPTIONS)

        # This must be last as we use this as an indicator for the
        # NODE_STATE_INTERVIEWED
        last = [zwave.ManufacturerSpecific, zwave.ManufacturerSpecific_Get]
        self.BatchCommandSubmitFilteredSlow([last], XMIT_OPTIONS)

    def BatchCommandSubmitFiltered(self, commands, priority, xmit):
        for cmd in commands:
            if not self.HasCommandClass(cmd[0]):
                continue

            def handler(m):
                logging.debug("@@handler invoked")
            try:
                raw_cmd = command.AssembleCommand(cmd)

            except:
                logging.error("cannot parse: %s", cmd)
                print("-" * 60)
                traceback.print_exc(file=sys.stdout)
                print("-" * 60)

            m = zmessage.MakeRawCommandWithId(self.n, raw_cmd, xmit)
            mesg = zmessage.Message(m, priority(self.n), handler, self.n)
            self._mq.EnqueueMessage(mesg)

        # if (num_sec > 0) {
        # MaybeRequestNewNonce(null);

    def BatchCommandSubmitFilteredSlow(self, commands, xmit):
        self.BatchCommandSubmitFiltered(commands, zmessage.NodePriorityLo, xmit)

    def BatchCommandSubmitFilteredFast(self, commands, xmit):
        self.BatchCommandSubmitFiltered(commands, zmessage.NodePriorityHi, xmit)

    def BatchCommandSubmitFilteredSecure(self, commands):
        for cmd in commands:
            assert self.CommandIsSecure(cmd)
            self._security_queue.Enqueue(cmd)
        self.MaybeRequestNewNonce()

    def MaybeRequestNewNonce(self):
        if len(self._security_queue) == 0:
            return

    def SendCommand(self, func, data, handler):
        raw = zmessage.MakeRawMessage(func, data)
        mesg = zmessage.Message(
            raw, zmessage.ControllerPriority(), handler, self.n)
        self._mq.EnqueueMessage(mesg)

    def SendSecureCommand(self, func, data, handler):
        raw = zmessage.MakeRawMessage(func, data)
        mesg = zmessage.Message(
            raw, zmessage.ControllerPriority(), handler, self.n)
        self._mq.EnqueueMessage(mesg)


NODES_HEADERS = [
    "#",
    "Name",
    "Type",
    "Id",
    "Chip",
    "Proto",
    "Lib",
    "Last Contact",
    "Meter",
    "Status",
    "Actions"]


class NodeSet(object):

    """NodeSet represents the collection of all nodes in a zwave network.

    All incoming application messages from the nodes (to the controller) are arrving in the
    message_queue (_mq).

    The class spawns a receiver thread, which listens to incoming messages and dispatches them
    to the node obect they are coming to.

    It also spawns a refresher Thread that will occasionally prompt nodes
    that has not been active for a while to send update requests.

    Outgoing messages from the controller to the nodes are put in the message_queue directly
    by the individual node objects.

    """

    def __init__(self, message_queue, event_cb, refresher_interval=60.0):
        self._mq = message_queue
        self._event_cb = event_cb
        self._refresh_interval = refresher_interval
        self.nodes = {}
        self._terminate = False
        self._receiver_thread = threading.Thread(
            target=self._NodesetReceiverThread,
            name="NodeSetReceive")
        self._receiver_thread.start()
        if refresher_interval != 0:
            self._refresher_thread = threading.Thread(
                target=self._NodesetRefresherThread,
                name="NodeRefresher")
            self._refresher_thread.start()
        else:
            self._refresher_thread = None

    def AllNodes(self):
        return self.nodes.values()

    def SummaryTabular(self):
        summary = {}
        for no, node in self.nodes.items():
            info = {}
            info["last_contact"] = node._last_contact
            info["state"] = node._state
            meters = [list(k) + list(v) for (k, v) in node._meters.items()]
            info["meters"] = meters
            sensors = [list(k) + [v] for (k, v) in node._sensors.items()]

            info["sensors"] = sensors
            summary[no] = info
        return summary

    def Summary(self):
        date = time.strftime("%Y/%m/%d %H:%M:%S")
        out = []
        for no, node in self.nodes.items():
            name = node.name
            last = time.strftime(
                "%Y/%m/%d %H:%M:%S", time.localtime(node._last_contact))
            state = node._state
            for (k, v) in node._meters.items():
                out.append(
                    [date, last, no, name, state, k[0], k[1], v[0], v[1]])
            for (k, v) in node._sensors.items():
                out.append([date, last, no, name, state, k[0], k[1], v, 0])
        return out

    def _NodesetRefresherThread(self):
        logging.warning("_NodesetRefresherThread started")
        time.sleep(self._refresh_interval)
        while not self._terminate:
            time.sleep(5)
            now = time.time()

            def slow(node):
                if not node._last_contact:
                    return False
                if node.IsSelf():
                    return False
                return now - node._last_contact > self._refresh_interval
            candidates = [node for node in self.nodes.values() if slow(node)]
            if candidates:
                node = random.choice(candidates)
                logging.warning("refreshing: [%d] %s", node.n, node.name)
                node.RefreshDynamicValues()

            def unknown(node):
                if node.IsSelf():
                    return False
                return node._state == command.NODE_STATE_NONE
            candidates = [
                node for node in self.nodes.values() if unknown(node)]
            if candidates:
                node = random.choice(candidates)
                logging.warning("ping: [%d] %s", node.n, node.name)
                node.Ping(1, True)
        logging.warning("_NodesetRefresherThread terminated")

    def GetNode(self, num):
        if num not in self.nodes:
            self.nodes[num] = Node(num, self._mq, self._event_cb)
        return self.nodes[num]

    def DropNode(self, num):
        del self.nodes[num]

    def Terminate(self):
        self._terminate = True
        self._mq.PutIncommingRawMessage(None)
        self._receiver_thread.join()
        if self._refresher_thread:
            self._refresher_thread.join()

    def HandleMessage(self, m):
        logging.info("NodeSet received: %s",  zmessage.PrettifyRawMessage(m))
        if m[3] == zwave.API_APPLICATION_COMMAND_HANDLER:
            _ = m[4]   # status
            n = m[5]
            size = m[6]
            node = self.GetNode(n)
            try:
                c = [int(x) for x in m[7:7 + size]]
                c = MaybePatchCommand(c)
                node.ProcessCommand(c)
            except:
                logging.error(
                    "Exception caught: cannot parse: %s", zmessage.PrettifyRawMessage(m))
                print("-" * 60)
                traceback.print_exc(file=sys.stdout)
                print("-" * 60)
            if node._state < command.NODE_STATE_DISCOVERED:
                node.Ping(3, True)
        elif m[3] == zwave.API_ZW_APPLICATION_UPDATE:
            logging.warning(
                "NodeSet received: %s",  zmessage.PrettifyRawMessage(m))
            kind = m[4]
            if kind == zwave.UPDATE_STATE_NODE_INFO_REQ_FAILED:
                logging.error(
                    "update request failed: %s", zmessage.PrettifyRawMessage(m))
            elif kind == zwave.UPDATE_STATE_NODE_INFO_RECEIVED:
                # the node is awake now and/or has changed values
                n = m[5]
                length = m[6]
                m = m[7: 7 + length]
                node = self.GetNode(n)
                node.ProcessNodeInfo(m)
            elif kind == zwave.UPDATE_STATE_SUC_ID:
                logging.warning("succ id updated")
            else:
                logging.error("unknown kind: %x", kind)
                assert False
        else:
            logging.error("unexpected message: %s", m)

    def _NodesetReceiverThread(self):
        logging.warning("_NodesetReceiverThread started")
        while True:
            m = self._mq.GetIncommingRawMessage()
            if m is None:
                break
            if m is None:
                break
            self.HandleMessage(m)
        logging.warning("_NodesetReceiverThread terminated")
