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

import tornado.autoreload
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket

from pyzwaver import command
from pyzwaver import zmessage
from pyzwaver import zcontroller
from pyzwaver import zdriver
from pyzwaver import znode
from pyzwaver import zwave

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
<button class=menu onclick='HandleTab(event)' data-param='tab-status'>Status</button>
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
<div class=tab id=tab-status></div>
<div class=tab id=tab-logs>
    <!-- see http://www.listjs.com/ -->
    <div id="driverlog">
    <table border=1>
    <!-- IMPORTANT, class="list" have to be at tbody -->
        <tbody class="list">
            <tr><td class="t"></td><td class="d"></td><td class="m"></td></tr>
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
var TAB_CONTROLLER = "tab-controller";
var TAB_ALL_NODES = "tab-all-nodes";
var TAB_ONE_NODE = "tab-one-node";
var TAB_STATUS = "tab-status";
var TAB_LOGS = "tab-logs";
var TAB_SLOW = "tab-slow";
var TAB_FAILED = "tab-failed";
var STATUS_FIELD = "status";
var ACTIVITY_FIELD = "activity"
var HISTORY_FIELD = "history";
var DRIVE_FIELD = "driver";
// Is there a literal notation for this?
var tabToDisplay = {};
tabToDisplay[TAB_CONTROLLER] = function() {return "/display/controller"; };
tabToDisplay[TAB_ALL_NODES] =  function() {return "/display/nodes"; };
tabToDisplay[TAB_ONE_NODE] = function() {return "/display/node/" + currentNode; };
tabToDisplay[TAB_STATUS] = function() {return "/display/status"; };
tabToDisplay[TAB_LOGS] = function() {return "/display/logs"; };
tabToDisplay[TAB_SLOW] = function() {return "/display/slow"; };
tabToDisplay[TAB_FAILED] = function() {return "/display/failed"; };

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
         document.getElementById(ACTIVITY_FIELD).innerHTML = val;
    } else if (tag == "S") {
         document.getElementById(STATUS_FIELD).innerHTML = val;
    } else if (tag == "E") {
         gEventHistory.push(val);
         gEventHistory.shift();
         document.getElementById(HISTORY_FIELD).innerHTML = gEventHistory.join("\\n");
    } else if (tag == "c") {
         var tab =  document.getElementById(TAB_CONTROLLER);
         tab.innerHTML = val;
    } else if (tag == "s") {
         var tab = document.getElementById(TAB_STATUS);
         tab.innerHTML = val;
    } else if (tag == "l") {
         var values = JSON.parse(val);
         var options = {
           valueNames: [ 't', 'd', 'm' ],
           //item: '<tr><td class="t"><td class="m"></td></td></tr>'
         };
         var lst = new List('driverlog', options, values);
    } else if (tag == "b") {
         var values = JSON.parse(val);
         var options = {
           valueNames: [ 'd', 't', 'm' ],
           //item: '<tr><td class="t"><td class="m"></td></td></tr>'
         };
         var lst = new List('driverslow', options, values);
    } else if (tag == "f") {
         var values = JSON.parse(val);
         var options = {
           valueNames: [ 'd', 't', 'm' ],
           //item: '<tr><td class="t"><td class="m"></td></td></tr>'
         };
         var lst = new List('driverfailed', options, values);
    } else if (tag == "a") {
         var tab = document.getElementById(TAB_ALL_NODES);
         tab.innerHTML = val;
    } else if (tag[0] == "o") {
        var node = tag.slice(1);
        if (node == currentNode) {
            tab = document.getElementById(TAB_ONE_NODE);
            tab.innerHTML = val;
        }
    } else if (tag == "d") {
         var tab = document.getElementById(DRIVE_FIELD);
         tab.innerHTML = val;
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
# A few globals
# ======================================================================

DRIVER = None
CONTROLLER = None
NODESET = None
DB = None

# ======================================================================
# WebSocker
# ======================================================================

SOCKETS = set()

def SendToSocket(mesg):
    #logging.error("Sending to socket: %d", len(SOCKETS))
    for s in SOCKETS:
        s.write_message(mesg)
    #logging.error("Sending to socket done: %d", len(SOCKETS))


def NodeEventCallback(n, event):
    SendToSocket("E:[%d] %s" % (n, event))
    if event == command.EVENT_VALUE_CHANGE:
        SendToSocket("E:[%d] %s" % (n, event))
        node = NODESET.GetNode(n)
        SendToSocket("o%d:" % n + RenderNode(node))
        SendToSocket("d:" + RenderDriver())

def ControllerEventCallback(action, event):
    SendToSocket("S:" + event)
    SendToSocket("A:" + action)
    if event == zcontroller.EVENT_UPDATE_COMPLETE:
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
    return  s % (action, cls, param, label)

def MakeNodeButton(node, action, label, cls=""):
    return MakeButton("HandleUrl", "/node/%d/%s" % (node.n, action), label, cls)

def MakeNodeButtonInput(node, action, label):
    return MakeButton("HandleUrlInput", "/node/%d/%s" % (node.n, action), label)

def MakeNodeButtonInputConfig(node, action, label):
    return MakeButton("HandleUrlInputConfig", "/node/%d/%s" % (node.n, action), label)

def MakeControllerButton(action, label):
    return MakeButton("HandleUrl", "/controller/%s" % action, label)

def MakeNodeRange(node, action, lo, hi):
   s = ("<input onchange='HandleChange(event)' data-param='/node/%d/%s/' class='multilevel' "
        "type=range min=%f max=%f value='%f'>")
   return s % (node.n, action, lo, hi, node.GetSensors().GetMultilevelSwitchLevel())

def RenderReading(value):
    v = value.value
    kind = value.kind
    unit = value.unit
    if kind == command.SENSOR_KIND_BATTERY:
        if v == 100:
            return ""
        else:
            unit = "% (battery)"
    elif kind == command.SENSOR_KIND_BASIC:
        return ""
    elif kind == command.SENSOR_KIND_SWITCH_MULTILEVEL:
        unit = "% (dimmer)"
    elif kind == command.SENSOR_KIND_SWITCH_BINARY:
        if v == 0:
            return "Off"
        else:
            return "On"
    else:
        if kind == command.SENSOR_KIND_RELATIVE_HUMIDITY and unit == "%":
            unit = "% (rel. hum.)"

    return "%.1f%s" % (v, unit)


def RenderAllReadings(values1, values2):
    seen = set()
    out = []
    for v in sorted(values1):
        out.append("<span class=reading>" + RenderReading(v) + "</span>")
        if v.unit:
            seen.add(v.unit)
    for v in sorted(values2):
        if v.unit in seen: continue
        out.append("<span class=reading>" + RenderReading(v) + "</span>")
    return out

def ClassSpecificNodeButtons(node):
    commands = node.GetCommands()
    out = []
    if commands.HasCommandClass(zwave.SwitchBinary):
        out.append(MakeNodeButton(node, "binary_switch/0", "Off"))
        out.append(MakeNodeButton(node, "binary_switch/255", "On"))
    if commands.HasCommandClass(zwave.SwitchMultilevel):
        out.append(MakeNodeRange(node, "multilevel_switch", 0, 100)),
    if commands.HasCommandClass(zwave.Meter):
        # reset
        pass
    return out

def MakeTableRowForNode(node, status_only, is_failed):
    global DB
    readings = RenderAllReadings(node.GetSensors().Readings(),
                                 node.GetMeters().Readings())
    buttons = []
    if not status_only:
        if not node.IsSelf():
            buttons.append(MakeNodeButton(node, "ping", "Ping"))
            buttons.append(MakeNodeButton(node, "refresh_dynamic", "Refresh"))
        buttons += ClassSpecificNodeButtons(node)
    basic = node.BasicInfo()
    name = DB.GetNodeName(node.n)
    if is_failed:
        basic["state"] = "FAILED"
    action = "HandleTabNode"
    param = str(node.n)
    #if node.IsSelf():
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
        "<td class=no>node: %(#)d</td>" % basic,
        "<td class=state>%(last_contact)s (%(state)s)</td>" % basic,
        "<td class=product>%(product)s</td>" % basic,
        "</tr>"]


def RenderNodes(as_status):
    global NODESET, CONTROLLER
    out = [
        "<table class=nodes>"
    ]
    nodes = CONTROLLER.nodes
    failed = CONTROLLER.failed_nodes
    for node in sorted(NODESET.nodes.values()):
        if node.n not in nodes: continue
        out.append("\n".join(MakeTableRowForNode(node, as_status, node.n in failed)))
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
       #MakeControllerButton("stop_add_node", "Abort"),
       "<p>",
       MakeControllerButton("add_controller_primary", "Add Primary Controller"),
       "&nbsp;",
       #MakeControllerButton("stop_add_controller_primary", "Abort"),
       "<p>",
       MakeControllerButton("remove_node", "Remove Node"),
       "&nbsp;",
       #MakeControllerButton("stop_remove_node", "Abort"),
       "<p>",
       MakeControllerButton("set_learn_mode", "Enter Learn Mode"),
       "&nbsp;",
       #MakeControllerButton("stop_set_learn_mode", "Abort"),
   ]
   return "\n".join(out)


def RenderDriver():
    global DRIVER
    return "<pre>" + str(DRIVER) + "</pre>"


def DriverLogs():
    global DRIVER
    out = []
    for t, sent, m in DRIVER.history._raw_history:
        ms = ".%03d" % int(1000 * (t - math.floor(t)))
        t = time.strftime("%H:%M:%S", time.localtime(t)) + ms
        d = sent and "=>" or "<="
        m = zmessage.PrettifyRawMessage(m)
        out.append({"t": t, "d": d, "m": m })
    return out

def DriverSlow():
    global DRIVER
    out = []
    for m in DRIVER.history._history:
        if not m.end: continue
        dur = int(1000.0 * (m.end - m.start))
        if dur < 300: continue
        d = "%4d%s" % (dur, "*" if m.aborted else " ")
        t = m.start
        ms = ".%03d" % int(1000 * (t - math.floor(t)))
        t = time.strftime("%H:%M:%S", time.localtime(t)) + ms
        m = zmessage.PrettifyRawMessage(m.payload)
        out.append({"d": d, "t": t, "m": m })
    return out

def DriverBad():
    global DRIVER
    out = []
    for m in DRIVER.history._history:
        if not m.end: continue
        if not m.aborted: continue
        dur = int(1000.0 * (m.end - m.start))
        d = "%4d" % dur
        t = m.start
        ms = ".%03d" % int(1000 * (t - math.floor(t)))
        t = time.strftime("%H:%M:%S", time.localtime(t)) + ms
        m = zmessage.PrettifyRawMessage(m.payload)
        out.append({"d": d, "t": t, "m": m })
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
                SendToSocket("a:" + RenderNodes(False))
            elif cmd == "status":
                SendToSocket("s:" + RenderNodes(True))
            elif cmd == "driver":
                SendToSocket("d:" + RenderDriver())
            elif cmd == "logs":
                SendToSocket("l:" + json.dumps(DriverLogs(), sort_keys=True,  indent=4))
            elif cmd == "slow":
                SendToSocket("b:" + json.dumps(DriverSlow(), sort_keys=True,  indent=4))
            elif cmd == "failed":
                SendToSocket("f:" + json.dumps(DriverBad(), sort_keys=True,  indent=4))

            elif cmd == "controller":
                SendToSocket("c:" + RenderController())
            elif cmd == "node":
                num = int(token.pop(0));
                if num == 0:
                    logging.error("no current node")
                else:
                    node = NODESET.GetNode(num)
                    SendToSocket("o%d:" % num + RenderNode(node))
            else:
                logging.error("unknown command %s", token)
        except:
            logging.error("cannot processed: %s", path[0])
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
        self.finish()


def RenderAssociationGroup(node: znode.Node, group: znode.AssociationGroup):
    no = group._no
    out = ["<tr>"
           "<th>", "Group %d %s [%d]:" % (no, group._name, group._capacity), "</th>",
           "<td>",
           ]
    for n in group._nodes:
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


def RenderNodeCommandClasses(node):
    out = ["<h2>Command Classes</h2>",
           MakeNodeButton(node, "refresh_commands", "Probe"),
           "<p>",
           "<table>",
    ]
    commands = node.GetCommands()
    for cls, version in commands.CommandVersions():
        name =  "%s [%d]" % (zwave.CMD_TO_STRING.get(cls, "UKNOWN:%d" % cls), cls)
        out += ["<tr><td>", name, "</td><td>", str(version), "</td></tr>"]
    out += ["</table>"]
    return out

def RenderNodeAssociations(node: znode.Node):
    out = ["<h2>Associations</h2>",
           MakeNodeButton(node, "refresh_assoc", "Probe"),
           "<p>",
           "<table>",
    ]
    associations = node.GetAssociations()
    for group in associations.Groups():
        out.append(RenderAssociationGroup(node, group))
    out += ["</table>"]
    return out


def RenderNodeParameters(node: znode.Node):
    compact = znode.CompactifyParams(node.GetParameters()._parameters)
    out = ["<h2>Configuration</h2>",
           MakeNodeButton(node, "refresh_parameters", "Probe"),
           "<br>",
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
        out += ["<tr><td>",  r, "</td><td>", "[%d]" % c, "</td><td>", str(d), "</td></tr>"]
    out += ["</table>"]
    return out

def RenderMiscValues(node):
    out = ["<h2>Misc Values</h2>",
            "<table>",
    ]
    for _, _, v in node.GetValues().GetAllTuples():
        out += ["<tr><td>", v.kind, "</td><td>", repr(v.value), "</td></tr>"]
    out += ["</table>",
            "<p>",
            ]
    return out


def RenderNode(node):
    global DB
    out = [
        "<pre>%s</pre>\n" % node.BasicString(),
        MakeNodeButton(node, "ping", "Ping Node"),
        "&nbsp;",
        MakeNodeButton(node, "refresh_dynamic", "Refresh Dynamic"),
        "&nbsp;",
        MakeNodeButton(node, "refresh_static", "Refresh Static"),
        "&nbsp;",
        MakeNodeButtonInput(node, "set_name/", "Change Name"),
        "<input type=text value='%s'>" % DB.GetNodeName(node.n),
        "<h2>Readings</h2>",
    ]
    out += RenderAllReadings(node.GetSensors().Readings(), node.GetMeters().Readings())
    out += ["<p>"]
    out += ClassSpecificNodeButtons(node)

    columns = [RenderNodeCommandClasses(node),
               RenderNodeParameters(node),
               RenderNodeAssociations(node),
               RenderMiscValues(node),
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
        global NODESET, DB
        token = path[0].split("/")
        logging.warning("NODE ACTION> %s", token)
        num = int(token.pop(0))
        node = NODESET.GetNode(num)
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
                node.Ping(3, True)
            elif cmd == "refresh_static":
                node.RefreshStaticValues()
            elif cmd == "refresh_dynamic":
                node.RefreshDynamicValues()
            elif cmd == "refresh_assoc":
                node.RefreshAssociations()
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
                print (num, size, value)
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
                    repr(CONTROLLER.nodes), repr(set(NODESET.nodes.keys())))

    # note, we are modifying NODESET.nodes while iterating
    for n in list(NODESET.nodes.keys()):
        if n not in CONTROLLER.nodes:
            logging.warning("dropping %d", n)
            NODESET.DropNode(n)
    for n in CONTROLLER.nodes:
        if n not in NODESET.nodes:
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
                CONTROLLER.StopChangeController(ChangeController)
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
                CONTROLLER.Update()
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
        global NODESET, DB
        summary = NODESET.SummaryTabular()
        for no, row in summary.items():
            row.name = DB.GetNodeName(no)
        self.write(json.dumps(summary, sort_keys=True,  indent=4))
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
        pass

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
        self._shelf =  shelve.open(shelf_path)
        atexit.register(self._shelf.close)

    def SetNodeName(self, num, name):
        key = "NodeName:%d" % num
        self._shelf[key] = name

    def GetNodeName(self, num,):
        key = "NodeName:%d" % num
        return self._shelf.get(key, "Node %d" % num)

def main():
    global DRIVER, CONTROLLER, NODESET, DB
    # note: this makes sure we have at least one handler
    # logging.basicConfig(level=logging.WARNING)
    #logging.basicConfig(level=logging.ERROR)

    tornado.options.parse_command_line()
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.setLevel(logging.WARNING)
    logger.setLevel(logging.ERROR)
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
    MQ =  zmessage.MessageQueue()
    device = zdriver.MakeSerialDevice(OPTIONS.serial_port)

    DRIVER = zdriver.Driver(device, MQ)
    NODESET = znode.NodeSet(MQ, NodeEventCallback, OPTIONS.node_auto_refresh_secs)
    CONTROLLER = zcontroller.Controller(MQ,
                                        ControllerEventCallback,
                                        pairing_timeout_secs=OPTIONS.pairing_timeout_secs)
    CONTROLLER.Initialize()
    CONTROLLER.WaitUntilInitialized()
    CONTROLLER.UpdateRoutingInfo()
    time.sleep(2)
    print(CONTROLLER)

    n = NODESET.GetNode(CONTROLLER.GetNodeId())
    n.InitializeExternally(CONTROLLER.props.product, CONTROLLER.props.library_type, True)

    for num in CONTROLLER.nodes:
        n = NODESET.GetNode(num)
        n.Ping(3, False)

    logging.warning("listening on port %d", OPTIONS.port)
    application.listen(OPTIONS.port)
    tornado.ioloop.IOLoop.instance().start()
    return 0

if __name__ == "__main__":
    sys.exit(main())
