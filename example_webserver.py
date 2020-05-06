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
Simple Webserver built on top of PyZwaver

Usage:
Run
    ./example_webserver --serial_port=<usb-zwave-device>
Common values for usb-zwave-device are:
    /dev/ttyUSBx
    /dev/ttyACMx
Then navigate to
    http:://localhost:55555
in your browser.
"""

import atexit
import datetime
import json
import logging
import math
import multiprocessing
import random
import shelve
import sys
import time
import traceback

import tornado.autoreload
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket

from pyzwaver import command_helper as ch
from pyzwaver import zmessage
from pyzwaver import zwave as z
from pyzwaver.command import NodeDescription
from pyzwaver.command_translator import CommandTranslator
from pyzwaver.controller import Controller, EVENT_UPDATE_COMPLETE
from pyzwaver.driver import Driver, MakeSerialDevice
from pyzwaver.node import Node, Nodeset, NODE_STATE_INTERVIEWED, NODE_STATE_DISCOVERED
from pyzwaver.value import CompactifyParams, SENSOR_KIND_SWITCH_BINARY, SENSOR_KIND_BATTERY, \
    SENSOR_KIND_RELATIVE_HUMIDITY

# ======================================================================

tornado.options.define("port",
                       default=55555,
                       type=int,
                       help="server port")

tornado.options.define("tasks",
                       default=4,
                       type=int,
                       help="size of task pool")

tornado.options.define("node_auto_refresh_secs",
                       default=300,
                       type=int,
                       help="seconds between refreshs")

tornado.options.define("pairing_timeout_secs",
                       default=30,
                       type=int,
                       help="seconds before pairing is auto aborted")

tornado.options.define("db",
                       default="pyzwaver.shelf",
                       type=str,
                       help="where state is persisted, e.g. node names, etc.")

tornado.options.define("serial_port",
                       default="/dev/ttyUSB0",
                       # default="/dev/ttyACM0",
                       type=str,
                       help="serial port")

OPTIONS = tornado.options.options


# ======================================================================
def TimeFormat(t):
    return time.strftime("%H:%M:%S", time.localtime(t))


def TimeFormatMs(t):
    ms = ".%03d" % int(1000 * (t - math.floor(t)))
    return TimeFormat(t) + ms


class Db(object):
    """Simple persistent storage"""

    def __init__(self, shelf_path):
        self._shelf = shelve.open(shelf_path)
        atexit.register(self._shelf.close)

    def SetNodeName(self, num, name):
        key = "NodeName:%d" % num
        self._shelf[key] = name

    def GetNodeName(self, num):
        key = "NodeName:%d" % num
        return self._shelf.get(key)


# ======================================================================
# A few globals
# ======================================================================

DRIVER: Driver = None
CONTROLLER: Controller = None
TRANSLATOR: CommandTranslator = None
NODESET: Nodeset = None
DB: Db = None

# ======================================================================
# WebSocket Stuff
#
# The webserver sends updates to the browser
#  d:  RenderDriver()
#  S:  event
#  A:  action
#  l:
#  c:  RenderController()
#  o#: RenderNode()
#
# ======================================================================

SOCKETS = set()


def SendToSocket(mesg: str):
    # logging.error("Sending to socket: %d", len(SOCKETS))
    for s in SOCKETS:
        s.write_message(mesg)
    # logging.error("Sending to socket done: %d", len(SOCKETS))


def SendToSocketJson(prefix: str, data: object):
    SendToSocket(prefix + json.dumps(data, sort_keys=True, indent=4))


def GetRandomNodeToRefresh():
    nn = list(CONTROLLER.nodes)
    for i in range(10):
        n = random.choice(nn)
        if DRIVER.OutQueueSizeForNode(n) > 0:
            continue
        if n == CONTROLLER.GetNodeId():
            continue
        return n
    return None


class NodeUpdater(object):
    """The NodeUpdater is registered with the TRANSLATOR and keeps
    track of those node which have changed.
    Every second updates will be emitted for those changed nodes.
    """

    def __init__(self):
        self._nodes_to_update = []
        self._update_driver = False
        self._epoch = 0

    def Periodic(self):
        try:
            if self._update_driver or DRIVER.HasInflight():
                SendToSocket("DRIVER:" + RenderDriver(DRIVER))
                # if there is stuff in flight the updates should come
                # automagically
                #
            # only update every 10 command or when queue is empty
            for n in self._nodes_to_update:
                if DRIVER.OutQueueSizeForNode(n) % 10 == 0:
                    node: Node = NODESET.GetNode(n)
                    data = json.dumps(RenderNode(node, DB),
                                      sort_keys=True, indent=4)
                    SendToSocket("ONE_NODE:%d:" % n + data)
            self._nodes_to_update.clear()

            n = GetRandomNodeToRefresh()
            if n is None:
                return
            node: Node = NODESET.GetNode(n)
            #logging.warning("refresh thread update: %d", n)

            if node.state < NODE_STATE_DISCOVERED:
                TRANSLATOR.Ping(n, 3, False, "refresher")
            elif node.state < NODE_STATE_INTERVIEWED:
                if random.random() < 0.1:
                    logging.warning("[%d] (%s) trigger static", n, node.state)
                    node.RefreshStaticValues()
            self._epoch += 1
        except Exception as e:
            logging.error(e)

    def put(self, n, _ts, _key, _values):
        # print ("got event ", n, _key, _values)
        # SendToSocket("E:[%d] %s" % (n, "@NO EVENT@"))
        if n not in self._nodes_to_update:
            self._nodes_to_update.append(n)
        self._update_driver = True


def ControllerEventCallback(action, event, _node):
    SendToSocket("STATUS:" + event)
    SendToSocket("ACTION:" + action)
    if event == EVENT_UPDATE_COMPLETE:
        SendToSocket("CONTROLLER:" + json.dumps(RenderController(CONTROLLER),
                                                sort_keys=True, indent=4))


class EchoWebSocket(tornado.websocket.WebSocketHandler):
    def open(self):
        logging.info("WebSocket opened")
        SOCKETS.add(self)

    # not really used but good for testing
    def on_message(self, message):
        logging.info("received socket message: %s", repr(message))

    def on_close(self):
        logging.info("WebSocket closed")
        SOCKETS.remove(self)


def RenderReading(kind, unit, val):
    if kind == SENSOR_KIND_BATTERY and val == 100:
        return ""
    elif kind == SENSOR_KIND_SWITCH_BINARY:
        if val == 0:
            return "Off"
        else:
            return "On"

    elif kind == SENSOR_KIND_RELATIVE_HUMIDITY and unit == "%":
        unit = "% (rel. hum.)"
    return "%.1f%s" % (val, unit)


def RenderReadings(readings):
    seen = set()
    out = []
    for key, kind, unit, val in sorted(readings):
        if unit in seen:
            continue
        out.append("<span class=reading>" +
                   RenderReading(kind, unit, val) + "</span>")
        seen.add(unit)
    return out


def RenderNodes(application_nodes, controller: Controller, db):
    out = []
    nodes = controller.nodes
    failed = controller.failed_nodes
    for node in sorted(application_nodes.nodes.values()):
        no_short = node.n if node.n <= 255 else (node.n >> 8)
        no_long = node.n if node.n > 255 else (node.n << 8)
        if no_short not in nodes:
            continue
        out.append((no_long, RenderNodeBrief(node, db, node.n in failed)))
    return [x[1] for x in sorted(out)]


def RenderController(controller: Controller):
    out = {
        "controller_basics": "<pre>%s</pre>" % controller.StringBasic(),
        "controller_routes": "<pre>%s</pre>" % controller.StringRoutes(),
        "controller_apis": "<pre>%s</pre>" % controller.props.StringApis(),
    }
    return out


def RenderDriver(driver: Driver):
    return str(driver)


def DriverLogs(driver: Driver):
    out = []
    for t, sent, m, comment in driver._raw_history:
        t = TimeFormatMs(t)
        d = sent and "=>" or "<="
        m = zmessage.PrettifyRawMessage(m)
        out.append({"t": t, "c": comment, "d": d, "m": m})
    return out


def DriverSlow(driver: Driver):
    out = []
    for m in driver.History():
        if not m.end:
            continue
        dur = int(1000.0 * (m.end - m.start))
        if dur < 300:
            continue
        d = "%4d%s" % (dur, "*" if m.WasAborted() else " ")
        t = TimeFormatMs(m.start)
        m = zmessage.PrettifyRawMessage(m.payload)
        out.append({"d": d, "t": t, "m": m})
    return out


def DriverBad(driver: Driver):
    out = []
    for m in driver.History():
        if not m.end:
            continue
        if not m.WasAborted():
            continue
        dur = int(1000.0 * (m.end - m.start))
        d = "%4d" % dur
        t = TimeFormatMs(m.start)
        m = zmessage.PrettifyRawMessage(m.payload)
        out.append({"d": d, "t": t, "m": m})
    return out


def GetControls(node: Node):
    is_switch = node.values.HasCommandClass(z.SwitchBinary)
    out = {
        "node_switch_on": is_switch,
        "node_switch_off": is_switch,
        "node_slide": node.values.HasCommandClass(z.SwitchMultilevel),
        "node_scene_refresh": node.values.HasCommandClass(z.SceneActuatorConf),
    }
    return out


def RenderAssociationGroup(no, group, name, _info, _lst):
    group_name = ""
    if name:
        group_name = name
    out = ["<tr>"
           "<th>", "Group %d %s [%d]:" % (
               no, group_name, group["count"]), "</th>",
           "<td>",
           ]
    for n in group["nodes"]:
        out += ["%d" % n,
                "&nbsp;"]

    out += ["</td>",
            "</tr>"]
    return "".join(out)


def RenderNodeCommandClasses(node: Node):
    out = ["<table>"]
    for cls, name, version in sorted(node.values.CommandVersions()):
        out += ["<tr><td>%s [%d]</td><td>%d</td></tr>" % (name, cls, version)]
    out += ["</table>"]
    return out


def RenderNodeAssociations(node: Node):
    out = [
        "<p>",
        "<table>",
    ]
    for no, group, info, lst, name in node.values.Associations():
        if group:
            out.append(RenderAssociationGroup(
                no, group, info, lst, name))
    out += ["</table>"]
    return out


def RenderNodeParameters(node: Node):
    compact = CompactifyParams(node.values.Configuration())
    out = ["<table>"]
    for a, b, c, d in sorted(compact):
        r = str(a)
        if a != b:
            r += " - " + str(b)
        out += ["<tr><td>", r, "</td><td>", "[%d]" %
                c, "</td><td>", str(d), "</td></tr>"]
    out += ["</table>"]
    return out


def RenderNodeScenes(node: Node):
    compact = CompactifyParams(node.values.SceneActuatorConfiguration())
    out = ["<table>"]
    for a, b, c, d in sorted(compact):
        r = str(a)
        if a != b:
            r += " - " + str(b)
        out += ["<tr><td>", r, "</td><td>", "[%d]" %
                c, "</td><td>", str(d), "</td></tr>"]
    out += ["</table>"]
    return out


def RenderMiscValues(node: Node):
    out = ["<table>"]
    for _, name, values in sorted(node.values.Values()):
        if name.endswith("Report"):
            name = name[:-6]
        if name.endswith("_"):
            name = name[:-1]
        out += ["<tr><td>", name, "</td><td>", repr(values), "</td></tr>"]
    out += ["</table>",
            "<p>",
            ]
    return out


def _ProductLink(_manu_id, prod_type, prod_id):
    return "http://www.google.com/search?q=site:products.z-wavealliance.org+0x%04x+0x%04x" % (
        prod_type, prod_id)


def RenderNodeBrief(node: Node, db: Db, _is_failed):
    readings = (RenderReadings(node.values.Sensors() +
                               node.values.Meters() +
                               node.values.MiscSensors()))
    state = node.state[3:]
    # TODO
    # if pnode.failed:
    #    state = "FAILED"
    age = "never"
    if node.last_contact:
        age = "%dm ago" % ((time.time() - node.last_contact) / 60.0)

    device_type = node.values.DeviceType()
    description = NodeDescription(device_type)
    db_name = db.GetNodeName(node.n)
    out = {
        "name": "Node %s" %
        node.Name() if db_name is None else "%s (%s)" %
        (db_name,
         node.Name()),
        "link": _ProductLink(
            *
            node.values.ProductInfo()),
        "switch_level": node.values.GetMultilevelSwitchLevel(),
        "controls": GetControls(node),
        "basics": "<pre>%s</pre>\n" %
        node.BasicString(),
        "readings": "\n".join(readings),
        "no": node.n,
        "state": state,
        "last_contact": "(%s) [%s]" %
        (TimeFormat(
            node.last_contact),
            age),
        "product": "%s (%s)" %
        (description,
         device_type),
    }

    return out


def RenderNode(node: Node, db):
    out = RenderNodeBrief(node, db, False)
    out["classes"] = "\n".join(RenderNodeCommandClasses(node))
    out["associations"] = "\n".join(RenderNodeAssociations(node))
    out["values"] = "\n".join(RenderMiscValues(node))
    out["configurations"] = "\n".join(RenderNodeParameters(node))
    out["scenes"] = "\n".join(RenderNodeScenes(node))
    return out


# ======================================================================
# URL Handlers
# ======================================================================
class BaseHandler(tornado.web.RequestHandler):
    """All handlers should inherit from this one
    """

    def initialize(self):
        pass


class NodeActionHandler(BaseHandler):
    """Single Node Actions"""

    def get(self, *path):
        global NODESET, DB
        token = path[0].split("/")
        logging.error("NODE ACTION> %s", token)
        num = int(token.pop(0))
        node: Node = NODESET.GetNode(num)
        cmd = token.pop(0)
        try:
            if cmd == "basic":
                p = int(token.pop(0))
                node.BatchCommandSubmitFilteredFast(ch.BasicSet(p))
            elif cmd == "binary_switch":
                p = int(token.pop(0))
                node.BatchCommandSubmitFilteredFast(ch.BinarySwitchSet(p))
            elif cmd == "multilevel_switch":
                p = int(token.pop(0))
                node.BatchCommandSubmitFilteredFast(ch.MultilevelSwitchSet(p))
            elif cmd == "ping":
                # force it
                TRANSLATOR.Ping(num, 3, True, "manual")
            elif cmd == "refresh_static":
                node.RefreshStaticValues()
            elif cmd == "refresh_semistatic":
                node.RefreshSemiStaticValues()
            elif cmd == "refresh_dynamic":
                node.RefreshDynamicValues()
            elif cmd == "refresh_commands":
                node.RefreshAllCommandVersions()
            elif cmd == "refresh_scenes":
                node.RefreshAllSceneActuatorConfigurations()
            elif cmd == "refresh_parameters":
                node.RefreshAllParameters()
            elif cmd == "association_add":
                group = int(token.pop(0))
                n = int(token.pop(0))
                node.BatchCommandSubmitFilteredFast(
                    ch.AssociationAdd(group, n))
            elif cmd == "change_parameter":
                num = int(token.pop(0))
                size = int(token.pop(0))
                value = int(token.pop(0))
                print(num, size, value)
                node.BatchCommandSubmitFilteredFast(
                    ch.ConfigurationSet(num, size, value))
            elif cmd == "association_remove":
                group = int(token.pop(0))
                n = int(token.pop(0))
                node.BatchCommandSubmitFilteredFast(
                    ch.AssociationRemove(group, n))
            elif cmd == "change_scene":
                scene = int(token.pop(0))
                level = int(token.pop(0))
                delay = int(token.pop(0))
                extra = int(token.pop(0))
                node.BatchCommandSubmitFilteredFast(
                    ch.SceneActuatorConfSet(scene, delay, level, extra))
            elif cmd == "set_name" and token:
                DB.SetNodeName(num, token.pop(0))
            elif cmd == "reset_meter":
                node.BatchCommandSubmitFilteredFast(ch.ResetMeter())
        except Exception as e:
            logging.error("cannot processed: %s", path[0])
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
        self.finish()


class ControllerActionHandler(BaseHandler):
    """Controller Actions"""

    def get(self, *path):
        global CONTROLLER
        token = path[0].split("/")
        logging.warning("CONTROLLER ACTION> %s", token)
        cmd = token.pop(0)
        try:
            if cmd == "add_node":
                CONTROLLER.StopAddNodeToNetwork(ControllerEventCallback)
                CONTROLLER.AddNodeToNetwork(ControllerEventCallback)
                CONTROLLER.StopAddNodeToNetwork(ControllerEventCallback)
            elif cmd == "stop_add_node":
                CONTROLLER.StopAddNodeToNetwork(ControllerEventCallback)
            elif cmd == "add_controller_primary":
                CONTROLLER.ChangeController(ControllerEventCallback)
                CONTROLLER.StopChangeController(ControllerEventCallback)
            elif cmd == "stop_add_controller_primary":
                CONTROLLER.StopChangeController(ControllerEventCallback)
            elif cmd == "remove_node":
                CONTROLLER.StopRemoveNodeFromNetwork(CONTROLLER)
                CONTROLLER.RemoveNodeFromNetwork(ControllerEventCallback)
                CONTROLLER.StopRemoveNodeFromNetwork(CONTROLLER)
            elif cmd == "stop_remove_node":
                CONTROLLER.StopRemoveNodeFromNetwork(ControllerEventCallback)
            elif cmd == "set_learn_mode":
                CONTROLLER.SetLearnMode()
                CONTROLLER.StopSetLearnMode(ControllerEventCallback)
            elif cmd == "stop_set_learn_mode":
                CONTROLLER.StopSetLearnMode(ControllerEventCallback)
            elif cmd == "soft_reset":
                CONTROLLER.SoftReset()
            elif cmd == "hard_reset":
                CONTROLLER.SetDefault()
                logging.error("Controller hard reset requires program restart")
                sys.exit(1)
            elif cmd == "refresh":
                CONTROLLER.Update(None)
            else:
                logging.error("unsupported command: %s", repr(token))
        except Exception as e:
            logging.error("cannot processed: %s", path[0])
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
        self.finish()


def GetUpdate(token):
    global NODESET, CONTROLLER, DRIVER, DB
    cmd = token[0]
    if cmd == "ALL_NODES":
        return RenderNodes(NODESET, CONTROLLER, DB)
    elif cmd == "DRIVER":
        return RenderDriver(DRIVER)
    elif cmd == "LOGS":
        return DriverLogs(DRIVER)
    elif cmd == "BAD":
        return DriverSlow(DRIVER)
    elif cmd == "FAILED":
        return DriverBad(DRIVER)
    elif cmd == "CONTROLLER":
        return RenderController(CONTROLLER)
    elif cmd == "ONE_NODE":
        num = int(token[1])
        if num == 0:
            logging.error("no current node")
        else:
            node = NODESET.GetNode(num)
            return RenderNode(node, DB)
    else:
        logging.error("unknown command %s", token)
        return ""


class JsonHandler(BaseHandler):
    """These are made available for debugging"""

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'GET,OPTIONS')

    def get(self, *path):
        token = path[0].split("/")
        logging.warning("JSON ACTION> %s", token)
        try:
            out = GetUpdate(token)
            self.write(json.dumps(out, sort_keys=True, indent=4))
        except BaseException:
            logging.error("cannot processed: %s", path[0])
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
        self.finish()

    def options(self):
        # no body
        self.set_status(204)
        self.finish()


class DisplayHandler(BaseHandler):
    """Misc Display Handlers"""

    def get(self, *path):
        token = path[0].split("/")
        logging.warning("DISPLAY ACTION> %s", token)
        try:
            tag = token[0]
            if tag == "ONE_NODE":
                tag += ":" + token[1]
            out = GetUpdate(token)
            SendToSocketJson(tag + ":", out)
        except Exception as e:
            logging.error("cannot processed: %s", path[0])
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
        self.finish()


# use --logging=none
# to disable the tornado logging overrides caused by
# tornado.options.parse_command_line(
class MyFormatter(logging.Formatter):
    def __init__(self):
        super().__init__()

    TIME_FMT = '%Y-%m-%d %H:%M:%S.%f'

    def format(self, record):
        return "%s%s %s:%s:%d %s" % (
            record.levelname[0],
            datetime.datetime.fromtimestamp(
                record.created).strftime(MyFormatter.TIME_FMT)[:-3],
            record.threadName,
            record.filename,
            record.lineno,
            record.msg % record.args)


_HANDLERS = [
    # Handles controller actions which will typically result in
    # an action and updates being sent to the websocket(s)
    (r"/controller/(.+)", ControllerActionHandler, {}),
    # Handles node actions which will typically result in
    # an action and updates being sent to the websocket(s)
    (r"/node/(.+)", NodeActionHandler, {}),
    # Request updates being sent to the websocket(s) without an action
    (r"/display/(.+)", DisplayHandler, {}),
    # for debugging
    ("/json/(.+)", JsonHandler, {}),
    (r"/updates", EchoWebSocket, {}),
    # Serves the main page
    ("/(.*)", tornado.web.StaticFileHandler,
     {"path": "Static/", "default_filename": "index.html"}),
]

_SETTINGS = {
    # "debug": True,
    "task_pool": multiprocessing.Pool(OPTIONS.tasks),
    # map static/xxx to Static/xxx
    "static_path": "Static/",
}


def main():
    global DRIVER, CONTROLLER, TRANSLATOR, NODESET, DB
    tornado.options.parse_command_line()
    # use --logging command line option to control verbosity
    # logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger()
    for h in logger.handlers:
        h.setFormatter(MyFormatter())

    # used to persist certain settings like node names
    logging.info("opening shelf: %s", OPTIONS.db)
    DB = Db(OPTIONS.db)

    application = tornado.web.Application(_HANDLERS, **_SETTINGS)

    logging.info("opening serial")
    device = MakeSerialDevice(OPTIONS.serial_port)

    DRIVER = Driver(device)
    CONTROLLER = Controller(
        DRIVER, pairing_timeout_secs=OPTIONS.pairing_timeout_secs)
    CONTROLLER.Initialize()
    CONTROLLER.WaitUntilInitialized()
    CONTROLLER.UpdateRoutingInfo()
    DRIVER.WaitUntilAllPreviousMessagesHaveBeenHandled()
    print(CONTROLLER)
    TRANSLATOR = CommandTranslator(DRIVER)
    NODESET = Nodeset(TRANSLATOR, CONTROLLER.GetNodeId())

    cp = CONTROLLER.props.product
    NODESET.put(
        CONTROLLER.GetNodeId(),
        time.time(),
        z.ManufacturerSpecific_Report,
        {'manufacturer': cp[0], 'type': cp[1], 'product': cp[2]})
    for n in CONTROLLER.nodes:
        TRANSLATOR.Ping(n, 3, False, "refresher")
    updater = NodeUpdater()
    TRANSLATOR.AddListener(updater)
    logging.warning("listening on port %d", OPTIONS.port)
    application.listen(OPTIONS.port)
    tornado.ioloop.PeriodicCallback(updater.Periodic, 2000).start()
    tornado.ioloop.IOLoop.instance().start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
