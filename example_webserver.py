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
    ./webserver --serial_port=<usb-zwave-device>
Common values for usb-zwave-device are:
    /dev/ttyUSBx
    /dev/ttyACMx
Then navigate to
    http:://localhost:55555
in your browser.
"""

# python import
import atexit
import datetime
import logging
import math
import multiprocessing
import shelve
import sys
import time
import traceback
import json
import threading

import tornado.autoreload
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket

from pyzwaver import value
from pyzwaver import zmessage
from pyzwaver import controller
from pyzwaver import driver
from pyzwaver import protocol_node
from pyzwaver import application_node
from pyzwaver import zwave as z

HTML = """
<html>
<head>
<base href="/" />
<link rel="stylesheet" type="text/css" href="%(css_path)s" />
<meta name="viewport" content="width=device-width" />
<script language="javascript" type="text/javascript" src="static/list.min.js"></script>
<title>%(title)s</title>
</head>

<body>
<div id=menu>
<button class=menu onclick='HandleTab(event)' data-param='tab-controller'>Controller</button>
<button class=menu onclick='HandleTab(event)' data-param='tab-all-nodes'>Nodes</button>
<button class=menu onclick='HandleTab(event)' data-param='tab-logs'>Logs</button>
<button class=menu onclick='HandleTab(event)' data-param='tab-slow'>Slow</button>
<button class=menu onclick='HandleTab(event)' data-param='tab-failed'>Failed</button>
Simple demo app using the pyzwaver library
</div>
<hr>

<div id=display-area>
<div class=tab id=tab-controller></div>
<div class=tab id=tab-all-nodes></div>
<div class=tab id=tab-one-node></div>
<div class=tab id=tab-logs>
    <!-- see http://www.listjs.com/ -->
    <div id="driverlog">
    <table border=1>
    <!-- IMPORTANT, class="list" have to be at tbody -->
        <tbody class="list">
            <tr><td class="t"></td><td class="c"></td><td class="d"></td><td class="m"></td></tr>
        </tbody>
    </table>
    </div>
</div>
<div class=tab id=tab-slow>
    <!-- see http://www.listjs.com/ -->
    <div id="driverslow">
    <table border=1>
    <!-- IMPORTANT, class="list" have to be at tbody -->
        <tbody class="list">
            <tr><td class="t"></td><td class="d"></td><td class="m"></td></tr>
        </tbody>
    </table>
    </div>
</div>

<div class=tab id=tab-failed>
    <!-- see http://www.listjs.com/ -->
    <div id="driverfailed">
    <table border=1>
    <!-- IMPORTANT, class="list" have to be at tbody -->
        <tbody class="list">
            <tr><td class="t"></td><td class="d"></td><td class="m"></td></tr>
        </tbody>
    </table>
    </div>
</div>

<hr>
<table>
<tr>
<td><pre id=driver></td>
<td><div id=activity></div><div id=status></div></td>
<td><pre id=history></pre></td>
</tr>
</table>
<hr>
<p><tt id=timestamp></tt></p>


<script>
"use strict";
// ============================================================
// The JS part of this demo is intentionally kept at a minimum.
// Whenever possible work his shifted to Python code.
// ============================================================

// Node that is currently shown in 'tab-one-node'
var currentNode = "0";

var gEventHistory = ["", "", "", "", "", ""];

var gDebug = 0;
// "enums" for tabs
const TAB_CONTROLLER = "tab-controller";
const TAB_ALL_NODES = "tab-all-nodes";
const TAB_ONE_NODE = "tab-one-node";
const TAB_LOGS = "tab-logs";
const TAB_SLOW = "tab-slow";
const TAB_FAILED = "tab-failed";
const STATUS_FIELD = "status";
const ACTIVITY_FIELD = "activity"
const HISTORY_FIELD = "history";
const DRIVE_FIELD = "driver";
// Is there a literal notation for this?
var tabToDisplay = {};
tabToDisplay[TAB_CONTROLLER] = function() {return "/display/controller"; };
tabToDisplay[TAB_ALL_NODES] =  function() {return "/display/nodes"; };
tabToDisplay[TAB_ONE_NODE] = function() {return "/display/node/" + currentNode; };
tabToDisplay[TAB_LOGS] = function() {return "/display/logs"; };
tabToDisplay[TAB_SLOW] = function() {return "/display/slow"; };
tabToDisplay[TAB_FAILED] = function() {return "/display/failed"; };

//  List visualization using the http://listjs.com/
const listLog = new List('driverlog', {valueNames: [ 't', 'c', 'd', 'm' ]});
const listSlow = new List('driverslow', {valueNames: [ 'd', 't', 'm' ]});
const listFailed = new List('driverfailed', {valueNames: [ 'd', 't', 'm' ]});


function OpenSocket() {
    var loc = window.location;
    var prefix = loc.protocol === 'https:' ? 'wss://' : 'ws://';
    return new WebSocket(prefix + loc.host + "/updates");
}

// Redraws work by triggering event in the Python code that will result
// in HTML fragments being sent to socket.
function SocketMessageHandler(e) {
    var colon = e.data.indexOf(":");
    var tag = e.data.slice(0, colon);
    var val = e.data.slice(colon + 1);
    if (gDebug) console.log("socket: " + tag);

    if (tag == "A") {
         // ACTION
         document.getElementById(ACTIVITY_FIELD).innerHTML = val;
    } else if (tag == "S") {
         // STATUS
         document.getElementById(STATUS_FIELD).innerHTML = val;
    } else if (tag == "E") {
         gEventHistory.push(val);
         gEventHistory.shift();
         document.getElementById(HISTORY_FIELD).innerHTML = gEventHistory.join("\\n");
    } else if (tag == "c") {
         // CONTROLLER
         document.getElementById(TAB_CONTROLLER).innerHTML = val;
    } else if (tag == "l") {
         // LOGS (list)
         var values = JSON.parse(val);
         listLog.clear();
         listLog.add(values);
    } else if (tag == "b") {
         // BAD (list)
         var values = JSON.parse(val);
         listSlow.clear();
         listSlow.add(values);
    } else if (tag == "f") {
         // FAILED (list)
         var values = JSON.parse(val);
         listFailed.clear();
         listFailed.add(values);
    } else if (tag == "a") {
         // ALL-NODES
         document.getElementById(TAB_ALL_NODES).innerHTML = val;
    } else if (tag[0] == "o") {
        // ONE-NODE
        var node = tag.slice(1);
        if (node == currentNode) {
            document.getElementById(TAB_ONE_NODE).innerHTML = val;
        }
    } else if (tag == "d") {
         // DRIVER
         document.getElementById(DRIVE_FIELD).innerHTML = val;
    }
}

// Show one tab while hiding the others.
function ShowTab(id) {
   var tabs = document.getElementsByClassName("tab");
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].style.display = "none";
   }
   document.getElementById(id).style.display = "block";
}

function HandleUrl(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    var param = ev.target.dataset.param;
    console.log("HandleUrl: " + param + ": " + ev.target);
    RequestURL("//" + window.location.host + param);
}

function HandleUrlInput(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    var param = ev.target.dataset.param;
    var input_elem = ev.target.parentElement.getElementsByTagName("input")[0];
    console.log("HandleUrl: " + param + ": " + input_elem.value + " " + ev.target);
    RequestURL("//" + window.location.host + param + input_elem.value);
}

function HandleUrlInputConfig(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    var param = ev.target.dataset.param;
    var p = ev.target.parentElement;
    var input_num = document.getElementById("num").value;
    var input_size = document.getElementById("size").value;
    var input_value = document.getElementById("value").value;

    console.log("HandleUrl: " + param + ": " + input_num + " " + input_size + " " + input_value);
    RequestURL("//" + window.location.host + param + input_num + "/" + input_size + "/" + input_value);
}

function HandleTab(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    var param = ev.target.dataset.param;
    console.log("HandleTab: " + param + ": " + ev.target);
    ShowTab(param);
    UpdateSome(param);
    UpdateDriverInfo();
    window.history.pushState({}, "", "#" + param);
}

function HandleTabNode(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    var param = ev.target.dataset.param;
    console.log("HandleTabNode: " + param + ": " + ev.target);
    ShowTab(TAB_ONE_NODE);
    currentNode = param;
    UpdateSome(TAB_ONE_NODE);
    UpdateDriverInfo();
    window.history.pushState({}, "", "#tab-one-node/" + param);
}

function HandleChange(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    var param = ev.target.dataset.param;
    var url = "//" + window.location.host + param + ev.target.value;
    console.log("change " + ev.target + " " +  url);
    RequestURL(url);
    return false;
}

function RequestURL(url) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.send();
}

function UpdateSome(tab) {
    RequestURL(tabToDisplay[tab]());
}

function UpdateDriverInfo() {
    RequestURL("/display/driver");
}

function ProcessUrlHash() {
  var hash = window.location.hash;
  if (hash == "") {
      hash = "tab-controller";
  } else {
     hash = hash.slice(1);
  }
  var tokens = hash.split("/");
  ShowTab(tokens[0]);
  if (tokens.length > 1) {
     currentNode = tokens[1];
     RequestURL("/display/node/" + currentNode);
  }
}

function DateToString(d) {
    console.log(d);
    function pad(n, digits) {
        var s = "" + n;
        while (s.length < digits)  s = '0' + s;
        return s;
    }
    var out = [pad(d.getUTCFullYear(), 4), '-',
               pad(d.getUTCMonth()+1, 2), '-',
               pad(d.getUTCDate(), 2),
               ' ',
               pad(d.getUTCHours(), 2), ':',
               pad(d.getUTCMinutes(), 2), ':',
               pad(d.getUTCSeconds(), 2),
               ' UTC',
             ];
    return out.join("");
}

// ============================================================
// Initialization
// ============================================================

window.onload = function () {
  ProcessUrlHash();
};


// we use window.parent to make this work even from within an iframe
window.parent.onpopstate = function(event) {
    ProcessUrlHash();
};

var gSocket = OpenSocket();

gSocket.onopen = function (e) {
  console.log("Connected to server socket");
};

gSocket.onmessage = SocketMessageHandler;

gSocket.onerror = function (e) {
   var m = "Cannot connect to Server: try reloading";
   console.log("ERROR: " + m);
   document.getElementById(STATUS_FIELD).innerHTML = m;
   tab.innerHTML = "ERROR: Cannot connect to Server: try reloading";
}

gSocket.onclose = function (e) {
    var m =  "Server connection lost: you must reload";
    console.log("ERROR: " + m);
    document.getElementById(STATUS_FIELD).innerHTML = m;
}

ShowTab(TAB_CONTROLLER);
for (var key in tabToDisplay) {
    UpdateSome(key);
}

UpdateDriverInfo();

var created = DateToString(new Date());

document.getElementById("timestamp").innerHTML = "" + created;

</script>

</body>
</html>
"""

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

tornado.options.define("css_style_file",
                       default="static/pyzwaver.css",
                       type=str,
                       help="style file path")

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


# ======================================================================
# A few globals
# ======================================================================

DRIVER: driver.Driver = None
CONTROLLER: controller.Controller = None
PROTOCOL_NODESET: protocol_node.NodeSet = None
APPLICATION_NODESET: application_node.ApplicationNodeSet = None
DB = None

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


def SendToSocket(mesg):
    # logging.error("Sending to socket: %d", len(SOCKETS))
    for s in SOCKETS:
        s.write_message(mesg)
    # logging.error("Sending to socket done: %d", len(SOCKETS))


class NodeUpdater(object):

    def __init__(self):
        self._nodes_to_update = set()
        self._update_controller = False
        timerThread = threading.Thread(target=self._refresh_thread)
        timerThread.daemon = True
        timerThread.start()

    def _refresh_thread(self):
        logging.warning("Refresher thread started")
        count = 0
        while True:
            if self._update_controller:
                SendToSocket("d:" + RenderDriver())
            if not APPLICATION_NODESET:
                continue
            for n in self._nodes_to_update:
                node = APPLICATION_NODESET.GetNode(n)
                SendToSocket(("o%d:" % n) + RenderNode(node))
            self._update_controller = False
            self._nodes_to_update.clear()
            if count % 20 == 0:
                for n in CONTROLLER.nodes:
                    node = APPLICATION_NODESET.GetNode(n)
                    if node.state < application_node.NODE_STATE_DISCOVERED:
                        node.protocol_node.Ping(3, False)
                        time.sleep(0.5)
                    elif node.state < application_node.NODE_STATE_INTERVIEWED:
                        node.RefreshStaticValues()
            count += 1
            time.sleep(1.0)

    def put(self, n, ts, key, values):
        # SendToSocket("E:[%d] %s" % (n, "@NO EVENT@"))
        self._nodes_to_update.add(n)
        self._update_controller = True


def ControllerEventCallback(action, event):
    SendToSocket("S:" + event)
    SendToSocket("A:" + action)
    if event == controller.EVENT_UPDATE_COMPLETE:
        SendToSocket("c:" + RenderController())


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


# ======================================================================
# URL Handlers
# ======================================================================


class BaseHandler(tornado.web.RequestHandler):
    """All handlers should inherit from this one
    """

    def initialize(self):
        pass


class MainHandler(BaseHandler):
    """ Handler for root path - simply redirects to /about
    """

    @tornado.web.asynchronous
    def get(self, *path):
        self.write(HTML % GetPrologArgs("Web-Zwaver"))
        self.finish()


def GetPrologArgs(title):
    return {
        "css_path": OPTIONS.css_style_file,
        "title": title
    }


def MakeButton(action, param, label, cls=""):
    if cls:
        cls = "class='" + cls + "' "
    s = "<button onclick='%s(event)' %sdata-param='%s'>%s</button>"
    return s % (action, cls, param, label)


def MakeNodeButton(node, action, label, cls=""):
    return MakeButton("HandleUrl", "/node/%d/%s" % (node.n, action), label, cls)


def MakeNodeButtonInput(node, action, label):
    return MakeButton("HandleUrlInput", "/node/%d/%s" % (node.n, action), label)


def MakeNodeButtonInputConfig(node, action, label):
    return MakeButton("HandleUrlInputConfig", "/node/%d/%s" % (node.n, action), label)


def MakeControllerButton(action, label):
    return MakeButton("HandleUrl", "/controller/%s" % action, label)


def MakeNodeRange(node: application_node.ApplicationNode, action, lo, hi):
    s = ("<input onchange='HandleChange(event)' data-param='/node/%d/%s/' class='multilevel' "
         "type=range min=%f max=%f value='%f'>")
    return s % (node.n, action, lo, hi, node.values.GetMultilevelSwitchLevel())


# TODO
def RenderReading(kind, unit, val):
    v = val["value"]["_value"]
    if kind == value.SENSOR_KIND_BATTERY:
        if v == 100:
            return ""
        else:
            unit = "% (battery)"
    elif kind == value.SENSOR_KIND_BASIC:
        return ""
    elif kind == value.SENSOR_KIND_SWITCH_MULTILEVEL:
        unit = "% (dimmer)"
    elif kind == value.SENSOR_KIND_SWITCH_BINARY:
        if v == 0:
            return "Off"
        else:
            return "On"
    else:
        if kind == value.SENSOR_KIND_RELATIVE_HUMIDITY and unit == "%":
            unit = "% (rel. hum.)"

    return "%.1f%s" % (v, unit)


def RenderAllReadings(values1, values2):
    seen = set()
    out = []
    for key, (kind, unit), val in sorted(values1):
        out.append("<span class=reading>" + RenderReading(kind, unit, val) + "</span>")
        seen.add(unit)
    for key, (kind, unit), val in sorted(values2):
        if unit in seen:
            continue
        out.append("<span class=reading>" + RenderReading(kind, unit, val) + "</span>")
    return out


def ClassSpecificNodeButtons(node: application_node.ApplicationNode):
    out = []
    if node.values.HasCommandClass(z.SwitchBinary):
        out.append(MakeNodeButton(node, "binary_switch/0", "Off"))
        out.append(MakeNodeButton(node, "binary_switch/255", "On"))
    if node.values.HasCommandClass(z.SwitchMultilevel):
        out.append(MakeNodeRange(node, "multilevel_switch", 0, 100)),
    if node.values.HasCommandClass(z.Meter):
        # reset
        pass
    return out


def MakeTableRowForNode(node: application_node.ApplicationNode, is_failed):
    global DB
    readings = RenderAllReadings(node.values.Sensors(),
                                 node.values.Meters())
    buttons = []
    if not node.IsSelf():
        buttons.append(MakeNodeButton(node, "ping", "Ping"))
    buttons += ClassSpecificNodeButtons(node)

    pnode = node.protocol_node
    state = node.state[2:]
    if pnode.failed:
        state = "FAILED"

    name = DB.GetNodeName(node.n)

    action = "HandleTabNode"
    param = str(node.n)
    # if node.IsSelf():
    #    action = "HandleTab"
    #    param = "tab-controller"
    return [
        "<tr>",
        "<td class=name>",
        MakeButton(action, param, name, cls="details"),
        "</td>",
        "<td colspan=3 class=readings>%s</td>" % " ".join(readings),
        "</tr>",
        #
        "<tr>",
        "<td>" + " ".join(buttons) + "</td>",
        "<td class=no>node: %d</td>" % node.n,
        "<td class=state>%s (%s)</td>" % (TimeFormat(pnode.last_contact), state),
        "<td class=product>%s (%s)</td>" % (pnode.device_description, pnode.device_type),
        "</tr>"]


def RenderNodes():
    global PROTOCOL_NODESET, CONTROLLER
    out = [
        "<table class=nodes>"
    ]
    nodes = CONTROLLER.nodes
    failed = CONTROLLER.failed_nodes
    for node in sorted(APPLICATION_NODESET.nodes.values()):
        if node.n not in nodes:
            continue
        out.append("\n".join(MakeTableRowForNode(node, node.n in failed)))
    out.append("</table>")
    return "\n".join(out)


def RenderController():
    out = [
        "<pre>%s</pre>\n" % CONTROLLER,
        "<p>",
        MakeControllerButton("soft_reset", "Soft Rest"),
        "&nbsp;",
        MakeControllerButton("hard_reset", "Hard Rest"),
        "<p>",
        MakeControllerButton("refresh", "Refresh"),
        "<h3>Pairing</h3>",
        MakeControllerButton("add_node", "Add Node"),
        "&nbsp;",
        # MakeControllerButton("stop_add_node", "Abort"),
        "<p>",
        MakeControllerButton("add_controller_primary", "Add Primary Controller"),
        "&nbsp;",
        # MakeControllerButton("stop_add_controller_primary", "Abort"),
        "<p>",
        MakeControllerButton("remove_node", "Remove Node"),
        "&nbsp;",
        # MakeControllerButton("stop_remove_node", "Abort"),
        "<p>",
        MakeControllerButton("set_learn_mode", "Enter Learn Mode"),
        "&nbsp;",
        # MakeControllerButton("stop_set_learn_mode", "Abort"),
    ]
    return "\n".join(out)


def RenderDriver():
    global DRIVER
    return "<pre>" + str(DRIVER) + "</pre>"


def DriverLogs():
    global DRIVER
    out = []
    for t, sent, m, comment in DRIVER._raw_history:
        t = TimeFormatMs(t)
        d = sent and "=>" or "<="
        m = zmessage.PrettifyRawMessage(m)
        out.append({"t": t, "c": comment, "d": d, "m": m})
    return out


def DriverSlow():
    global DRIVER
    out = []
    for m in DRIVER._history:
        if not m.end: continue
        dur = int(1000.0 * (m.end - m.start))
        if dur < 300: continue
        d = "%4d%s" % (dur, "*" if m.WasAborted() else " ")
        t = TimeFormatMs(m.start)
        m = zmessage.PrettifyRawMessage(m.payload)
        out.append({"d": d, "t": t, "m": m})
    return out


def DriverBad():
    global DRIVER
    out = []
    for m in DRIVER._history:
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


class DisplayHandler(BaseHandler):
    """Misc Display Hanlders - except for node"""

    @tornado.web.asynchronous
    def get(self, *path):
        token = path[0].split("/")
        logging.warning("DISPLAY ACTION> %s", token)
        cmd = token.pop(0)
        try:
            if cmd == "nodes":
                SendToSocket("a:" + RenderNodes())
            elif cmd == "driver":
                SendToSocket("d:" + RenderDriver())
            elif cmd == "logs":
                SendToSocket("l:" + json.dumps(DriverLogs(), sort_keys=True, indent=4))
            elif cmd == "slow":
                SendToSocket("b:" + json.dumps(DriverSlow(), sort_keys=True, indent=4))
            elif cmd == "failed":
                SendToSocket("f:" + json.dumps(DriverBad(), sort_keys=True, indent=4))

            elif cmd == "controller":
                SendToSocket("c:" + RenderController())
            elif cmd == "node":
                num = int(token.pop(0))
                if num == 0:
                    logging.error("no current node")
                else:
                    node = APPLICATION_NODESET.GetNode(num)
                    SendToSocket("o%d:" % num + RenderNode(node))
            else:
                logging.error("unknown command %s", token)
        except:
            logging.error("cannot processed: %s", path[0])
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
        self.finish()


def RenderAssociationGroup(node: application_node.ApplicationNode, no, group, name, info, lst):
    group_name = ""
    if name:
        group_name = name["name"]
    out = ["<tr>"
           "<th>", "Group %d %s [%d]:" % (no, group_name, group["count"]), "</th>",
           "<td>",
           ]
    for n in group["nodes"]:
        out += ["%d" % n,
                MakeNodeButton(node, "association_remove/%d/%d" % (no, n), "X", "remove"),
                "&nbsp;"]

    out += ["</td>",
            "<td>",
            MakeNodeButtonInput(node, "association_add/%d/" % no, "Add Node"),
            "<input type=number min=0 max=232 value=0>",
            "</td>",
            "</tr>"]
    return "".join(out)


def RenderNodeCommandClasses(node: application_node.ApplicationNode):
    out = ["<h2>Command Classes</h2>",
           MakeNodeButton(node, "refresh_commands", "Probe All"),
           "<p>",
           "<table>",
           ]
    for cls, name, version in sorted(node.values.CommandVersions()):
        out += ["<tr><td>%s [%d]</td><td>%d</td></tr>" % (name, cls, version)]
    out += ["</table>"]
    return out


def RenderNodeAssociations(node: application_node.ApplicationNode):
    out = ["<h2>Associations</h2>",
           "<p>",
           "<table>",
           ]
    for no, group, info, lst, name in node.values.Associations():
        if group:
            out.append(RenderAssociationGroup(node, no, group, info, lst, name))
    out += ["</table>"]
    return out


def RenderNodeParameters(node: application_node.ApplicationNode):
    compact = value.CompactifyParams(node.values.Configuration())
    out = ["<h2>Configuration</h2>",
           MakeNodeButton(node, "refresh_parameters", "Probe All"),
           "&nbsp;",
           MakeNodeButtonInputConfig(node, "change_parameter/", "Change"),
           "no <input id=num type='number' name='no' value=0 min=1 max=232 style='width: 3em'>",
           "size <select id=size name='size'>",
           "<option value='1'>1</option>",
           "<option value='2'>2</option>",
           "<option value='4'>4</option>",
           "</select>",
           "value <input id=value type='number' name='val' value=0 style='width: 7em'>",
           "<p>",
           "<table>",
           ]
    for a, b, c, d in sorted(compact):
        r = str(a)
        if a != b:
            r += " - " + str(b)
        out += ["<tr><td>", r, "</td><td>", "[%d]" % c, "</td><td>", str(d), "</td></tr>"]
    out += ["</table>"]
    return out


def RenderMiscValues(node: application_node.ApplicationNode):
    out = ["<h2>Misc Values</h2>",
           "<table>",
           ]
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


def RenderNode(node: application_node.ApplicationNode):
    global DB
    out = [
        "<pre>%s</pre>\n" % node.BasicString(),
        MakeNodeButton(node, "ping", "Ping Node"),
        "&nbsp;",
        MakeNodeButton(node, "refresh_dynamic", "Refresh Dynamic"),
          "&nbsp;",
        MakeNodeButton(node, "refresh_semistatic", "Refresh Semi Static"),
        "&nbsp;",
        MakeNodeButton(node, "refresh_static", "Refresh Static"),
        "&nbsp;",
        MakeNodeButtonInput(node, "set_name/", "Change Name"),
        "<input type=text value='%s'>" % DB.GetNodeName(node.n),
        "<p>"
        "<h2>Readings</h2>",
    ]
    out += RenderAllReadings(node.values.Sensors(), node.values.Meters())
    out += ["<p>"]
    out += ClassSpecificNodeButtons(node)

    columns = [
        RenderNodeCommandClasses(node) + RenderNodeAssociations(node),
        RenderMiscValues(node) + RenderNodeParameters(node),
    ]

    out += ["<table class=node-sections width='100%'>",
            "<tr>"
            ]
    for c in columns:
        out += ["<td class=section>"] + c + ["</td>"]
    out += ["</tr></table>"]
    return "\n".join(out)


class NodeActionHandler(BaseHandler):
    """Single Node Actions"""

    def get(self, *path):
        global APPLICATION_NODESET, DB
        token = path[0].split("/")
        logging.warning("NODE ACTION> %s", token)
        num = int(token.pop(0))
        node: application_node.ApplicationNode = APPLICATION_NODESET.GetNode(num)
        cmd = token.pop(0)
        try:
            if cmd == "basic":
                p = int(token.pop(0))
                node.SetBasic(p)
            elif cmd == "binary_switch":
                p = int(token.pop(0))
                node.SetBinarySwitch(p)
            elif cmd == "multilevel_switch":
                p = int(token.pop(0))
                node.SetMultilevelSwitch(p)
            elif cmd == "ping":
                # force it
                node.protocol_node.Ping(3, True)
            elif cmd == "refresh_static":
                node.RefreshStaticValues()
            elif cmd == "refresh_semistatic":
                node.RefreshSemiStaticValues()
            elif cmd == "refresh_dynamic":
                node.RefreshDynamicValues()
            elif cmd == "refresh_commands":
                node.RefreshAllCommandVersions()
            elif cmd == "refresh_parameters":
                node.RefreshAllParameters()
            elif cmd == "association_add":
                group = int(token.pop(0))
                n = int(token.pop(0))
                node.AssociationAdd(group, n)
            elif cmd == "change_parameter":
                num = int(token.pop(0))
                size = int(token.pop(0))
                value = int(token.pop(0))
                print(num, size, value)
                node.SetConfigValue(num, size, value)
            elif cmd == "association_remove":
                group = int(token.pop(0))
                n = int(token.pop(0))
                node.AssociationRemove(group, n)
            elif cmd == "set_name" and token:
                DB.SetNodeName(num, token.pop(0))
            elif cmd == "reset_meter":
                node.ResetMeter()
        except:
            logging.error("cannot processed: %s", path[0])
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
        self.finish()


def BalanceNodes(m):
    logging.warning("balancing contoller %s vs nodeset %s",
                    repr(CONTROLLER.nodes), repr(set(PROTOCOL_NODESET.nodes.keys())))

    # note, we are modifying NODESET.nodes while iterating
    for n in list(APPLICATION_NODESET.nodes.keys()):
        if n not in CONTROLLER.nodes:
            logging.warning("dropping %d", n)
            # TODO:
            APPLICATION_NODESET.DropNode(n)
    for n in CONTROLLER.nodes:
        if n not in APPLICATION_NODESET.nodes:
            logging.warning("request node info for %d", n)
            CONTROLLER.RequestNodeInfo(n)


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
        except:
            logging.error("cannot processed: %s", path[0])
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
        self.finish()


class JsonHandler(BaseHandler):

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'GET,OPTIONS')

    @tornado.web.asynchronous
    def get(self):
        global APPLICATION_NODESET, DB
        summary = APPLICATION_NODESET.SummaryTabular()
        for no, row in summary.items():
            row.name = DB.GetNodeName(no)
        self.write(json.dumps(summary, sort_keys=True, indent=4))
        self.finish()

    @tornado.web.asynchronous
    def options(self):
        # no body
        self.set_status(204)
        self.finish()


HANDLERS = [
    ("/", MainHandler, {}),
    ("/json", JsonHandler, {}),
    (r"/controller/(.+)", ControllerActionHandler, {}),
    (r"/node/(.+)", NodeActionHandler, {}),
    (r"/display/(.+)", DisplayHandler, {}),
    (r"/updates", EchoWebSocket, {}),
]


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
            datetime.datetime.fromtimestamp(record.created).strftime(MyFormatter.TIME_FMT)[:-3],
            record.threadName,
            record.filename,
            record.lineno,
            record.msg % record.args)


class Db:
    """Simple persistent storage"""

    def __init__(self, shelf_path):
        self._shelf = shelve.open(shelf_path)
        atexit.register(self._shelf.close)

    def SetNodeName(self, num, name):
        key = "NodeName:%d" % num
        self._shelf[key] = name

    def GetNodeName(self, num, ):
        key = "NodeName:%d" % num
        return self._shelf.get(key, "Node %d" % num)


def main():
    global DRIVER, CONTROLLER, PROTOCOL_NODESET, APPLICATION_NODESET, DB
    # note: this makes sure we have at least one handler
    # logging.basicConfig(level=logging.WARNING)
    # logging.basicConfig(level=logging.ERROR)

    tornado.options.parse_command_line()
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.setLevel(logging.WARNING)
    # logger.setLevel(logging.ERROR)
    for h in logger.handlers:
        h.setFormatter(MyFormatter())

    logging.info("opening shelf: %s", OPTIONS.db)
    DB = Db(OPTIONS.db)

    application = tornado.web.Application(
        HANDLERS,
        debug=True,
        task_pool=multiprocessing.Pool(OPTIONS.tasks),
        # map static/xxx to Static/xxx
        static_path="Static/",
    )

    logging.info("opening serial")
    device = driver.MakeSerialDevice(OPTIONS.serial_port)

    DRIVER = driver.Driver(device)
    CONTROLLER = controller.Controller(DRIVER, pairing_timeout_secs=OPTIONS.pairing_timeout_secs)
    CONTROLLER.Initialize()
    CONTROLLER.WaitUntilInitialized()
    CONTROLLER.UpdateRoutingInfo()
    time.sleep(2)
    print(CONTROLLER)
    PROTOCOL_NODESET = protocol_node.NodeSet(DRIVER, CONTROLLER.GetNodeId())
    APPLICATION_NODESET = application_node.ApplicationNodeSet(PROTOCOL_NODESET)

    PROTOCOL_NODESET.AddListener(APPLICATION_NODESET)
    PROTOCOL_NODESET.AddListener(NodeUpdater())

    # TODO n.InitializeExternally(CONTROLLER.props.product, CONTROLLER.props.library_type, True)

    logging.warning("listening on port %d", OPTIONS.port)
    application.listen(OPTIONS.port)
    tornado.ioloop.IOLoop.instance().start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
