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

from pyzwaver.value import CompactifyParams, SENSOR_KIND_SWITCH_BINARY, SENSOR_KIND_BATTERY, \
    SENSOR_KIND_RELATIVE_HUMIDITY
from pyzwaver import zmessage
from pyzwaver.controller import Controller, EVENT_UPDATE_COMPLETE
from pyzwaver.driver import Driver, MakeSerialDevice
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
%(body)s

<script>
%(script)s
</script>

</body>
</html>
"""

# language=HTML
BODY = """
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

<!-- ============================================================ -->
<div class=tab id=tab-controller>

<h2>Basics</h2>
<div id=controller_basics></div>

<h2>Connectivity</h2>
<div id=controller_routes></div>

<h2>Actions</h2>
<div id=controller_buttons</div>
<button onclick='HandleUrl(event)' data-param='/controller/refresh'>
    Refresh</button>
&nbsp;
<button onclick='HandleUrl(event)' data-param='/controller/soft_reset'>
    Soft Reset</button>
&nbsp;
<button onclick='HandleUrl(event)' data-param='/controller/hard_reset'>
    Hard Reset</button>
</div>

<h2>Pairing</h2>

<button onclick='HandleUrl(event)' data-param='/controller/add_node'>
    Add Node</button>
&nbsp;
<button onclick='HandleUrl(event)' data-param='/controller/remove_node'>
    Remove Node</button>
&nbsp;
<button onclick='HandleUrl(event)' data-param='/controller/add_controller_primary'>
    Add Primary Controller</button>
&nbsp;
<button onclick='HandleUrl(event)' data-param='/controller/set_learn_mode'>
    Enter Learn Mode</button>
    
<h2>APIs</h2>
<div id=controller_apis></div>
    
</div>

<!-- ============================================================ -->
<div class=tab id=tab-all-nodes></div>


<!-- ============================================================ -->
<div class=tab id=tab-one-node>

<h2>Basics</h2>
<div id=one_node_basics></div>

<h2>Maintenance</h2>
<div id=one_node_maintenance>

<button onclick='HandleAction(event)' data-param='/node/<CURRENT>/ping'>
    Ping Node</button>
&nbsp;
<button onclick='HandleAction(event)' data-param='/node/<CURRENT>/refresh_dynamic'>
    Refresh Dynamic</button>
&nbsp;
<button onclick='HandleAction(event)' data-param='/node/<CURRENT>/refresh_semistatic'>
    Refresh Semi Static</button>
&nbsp;
<button onclick='HandleAction(event)' data-param='/node/<CURRENT>/refresh_static'>
    Refresh Static</button>

<p>

<button onclick='HandleAction(event)' data-param='/node/<CURRENT>/refresh_commands'>
    Probe Command</button>
&nbsp;
<button onclick='HandleAction(event)' data-param='/node/<CURRENT>/refresh_parameters'>
    Probe Configuration</button>
&nbsp;
<button onclick='HandleAction(event)' data-param='/node/<CURRENT>/refresh_scenes'>
    Probe Scenes</button>
&nbsp;

<p>
<button onclick='HandleAction(event)' 
        data-param='/node/<CURRENT>/set_name/'
        data-args='one_node_name'>
    Change Name</button>
    <input type=text id=one_node_name>
<p> 

<button onclick='HandleAction(event)' 
        data-param='/node/<CURRENT>/change_parameter/'
        data-args='one_node_config_num,one_node_config_size,one_node_config_value'>
    Change Config Param</button>    
no <input id=one_node_config_num type='number' name='no' value=0 min=1 max=232 style='width: 3em'>
size <select id=one_node_config_size name='size'>
<option value='1'>1</option>
<option value='2'>2</option>
<option value='4'>4</option>
</select>
value <input id=one_node_config_value type='number' name='val' value=0 style='width: 7em'>

<p>

<button onclick='HandleAction(event)' 
        data-param='/node/<CURRENT>/change_scene/'
        data-args='one_node_scene_num,one_node_scene_level,one_node_scene_delay,one_node_scene_extra'>
    Change Scene</button>    
no <input id=one_node_scene_num type='number' name='num' value=1 min=1 max=255 style='width: 3em'>
level <input id=one_node_scene_level type='number' name='level' value=0 min=0 max=255 style='width: 3em'>
delay <input id=one_node_scene_delay type='number' name='delay' value=0 min=0 max=255 style='width: 3em'>

<select id=one_node_scene_extra name='extra'>
<option value='128'>on</option>
<option value='0'>off</option>
</select>

<h2>Actions</h2>
<div id=one_node_actions>


<span id=one_node_switch>
<button onclick='HandleAction(event)' data-param='/node/<CURRENT>/binary_switch/0'>
    Off</button>
&nbsp;
<button onclick='HandleAction(event)' data-param='/node/<CURRENT>/binary_switch/100'>
    On</button>
&nbsp;
</span>

<input id=one_node_slide 
       onchange='HandleChange(event)' 
       data-param='/node/<CURRENT>/multilevel_switch/' 
       class='multilevel' 
       type=range min=0 max=100 value=0>
</span>
  

</div>

<h2>Readings</h2>
<div id=one_node_readings></div>
 
<h2>Command Classes</h2>
<div id=one_node_classes></div>

<h2>Associations</h2>
<div id=one_node_associations></div>

<h2>Values</h2>
<div id=one_node_values></div>

<h2>Configuration</h2>
<div id=one_node_configurations></div>

<h2>Scenes</h2>
<div id=one_node_scenes></div>
</div>

<!-- ============================================================ -->
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

<!-- ============================================================ -->
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

<!-- ============================================================ -->
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
"""

# language=JShell
SCRIPT = """
"use strict";
// ============================================================
// The JS part of this demo is intentionally kept at a minimum.
// Whenever possible work his shifted to Python code.
// ============================================================

// Node that is currently shown in 'tab-one-node'
var currentNode = "0";

let gEventHistory = ["", "", "", "", "", ""];

const  gDebug = 0;
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

const  tabToDisplay = {
    [TAB_CONTROLLER]: function() {return "/display/controller"; },
    [TAB_ALL_NODES]:  function() {return "/display/nodes"; },
    [TAB_ONE_NODE]:   function() {return "/display/node/" + currentNode; },
    [TAB_LOGS]:       function() {return "/display/logs"; },
    [TAB_SLOW]:       function() {return "/display/slow"; },
    [TAB_FAILED]:     function() {return "/display/failed"; },
};


//  List visualization using the http://listjs.com/
const listLog = new List('driverlog', {valueNames: [ 't', 'c', 'd', 'm' ]});
const listSlow = new List('driverslow', {valueNames: [ 'd', 't', 'm' ]});
const listFailed = new List('driverfailed', {valueNames: [ 'd', 't', 'm' ]});


function OpenSocket() {
    const loc = window.location;
    const prefix = loc.protocol === 'https:' ? 'wss://' : 'ws://';
    return new WebSocket(prefix + loc.host + "/updates");
}

// Redraws work by triggering event in the Python code that will result
// in HTML fragments being sent to socket.
function SocketMessageHandler(e) {
    const colon = e.data.indexOf(":");
    const tag = e.data.slice(0, colon);
    const val = e.data.slice(colon + 1);
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
         const values = JSON.parse(val);
         document.getElementById('controller_basics').innerHTML = 
             values.controller_basics;
         document.getElementById('controller_routes').innerHTML = 
             values.controller_routes;
         document.getElementById('controller_apis').innerHTML = 
             values.controller_apis;
    } else if (tag == "l") {
         // LOGS (list)
         const values = JSON.parse(val);
         listLog.clear();
         listLog.add(values);
    } else if (tag == "b") {
         // BAD (list)
         const values = JSON.parse(val);
         listSlow.clear();
         listSlow.add(values);
    } else if (tag == "f") {
         // FAILED (list)
         const values = JSON.parse(val);
         listFailed.clear();
         listFailed.add(values);
    } else if (tag == "a") {
         // ALL-NODES
         document.getElementById(TAB_ALL_NODES).innerHTML = val;
    } else if (tag[0] == "o") {
        // ONE-NODE
        const values = JSON.parse(val);
        const node = tag.slice(1);
        if (node == currentNode) {
            document.getElementById("one_node_basics").innerHTML =
                values.one_node_basics;
            document.getElementById("one_node_classes").innerHTML =
                values.one_node_classes;
            document.getElementById("one_node_associations").innerHTML =
                values.one_node_associations;
            document.getElementById("one_node_values").innerHTML =
                values.one_node_values;
            document.getElementById("one_node_configurations").innerHTML =
                values.one_node_configurations;
            document.getElementById("one_node_readings").innerHTML =
                values.one_node_readings;
            document.getElementById("one_node_scenes").innerHTML =
                values.one_node_scenes;
                
            document.getElementById("one_node_name").value = 
                values.one_node_name;
            document.getElementById("one_node_slide").value = 
                values.one_node_switch_level;
            for (let key in values.one_node_controls) {
                 let e = document.getElementById(key);
                 let val = values.one_node_controls[key];
                 console.log(`$e: ${key} -> ${val}`);
                 e.hidden = ! val;
            }
        }
    } else if (tag == "d") {
         // DRIVER
         document.getElementById(DRIVE_FIELD).innerHTML = val;
    }
}

// Show one tab while hiding the others.
function ShowTab(id) {
   const tabs = document.getElementsByClassName("tab");
    for (let i = 0; i < tabs.length; i++) {
        tabs[i].style.display = "none";
   }
   document.getElementById(id).style.display = "block";
}

function RequestURL(url) {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.send();
}

function RequestActionURL(param, args) {
    const base = "//" + window.location.host + param;
    RequestURL(base + args.join("/"));
}

function HandleAction(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const param = ev.target.dataset.param.replace("<CURRENT>", currentNode);
    let args= [];
    const elem_list = ev.target.dataset.args;
    if (elem_list) {
        for (let elem of elem_list.split(',')) {
            args.push(document.getElementById(elem).value);
        }
    }
    console.log("HandleUrl: " + param + ": " + args);
    RequestActionURL(param, args);
}


function HandleUrl(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const param = ev.target.dataset.param.replace("<CURRENT>", currentNode);
    console.log("HandleUrl: " + param + ": " + ev.target);
    RequestActionURL(param, []);
}

function HandleUrlInput(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const param = ev.target.dataset.param.replace("<CURRENT>", currentNode);
    const input_elem = ev.target.parentElement.getElementsByTagName("input")[0];
    console.log("HandleUrl: " + param + ": " + input_elem.value + " " + ev.target);
    RequestActionURL(param, [input_elem.value]);
}


function HandleTab(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const param = ev.target.dataset.param;
    console.log("HandleTab: " + param + ": " + ev.target);
    ShowTab(param);
    UpdateSome(param);
    UpdateDriverInfo();
    window.history.pushState({}, "", "#" + param);
}

function HandleTabNode(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const param = ev.target.dataset.param;
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
    const param = ev.target.dataset.param.replace("<CURRENT>", currentNode);
    const url = "//" + window.location.host + param + ev.target.value;
    console.log("change " + ev.target + " " +  url);
    RequestURL(url);
    return false;
}



function UpdateSome(tab) {
    RequestURL(tabToDisplay[tab]());
}

function UpdateDriverInfo() {
    RequestURL("/display/driver");
}

function ProcessUrlHash() {
  let hash = window.location.hash;
  if (hash == "") {
      hash = "tab-controller";
  } else {
     hash = hash.slice(1);
  }
  const tokens = hash.split("/");
  ShowTab(tokens[0]);
  if (tokens.length > 1) {
     currentNode = tokens[1];
     RequestURL("/display/node/" + currentNode);
  }
}

function DateToString(d) {
    console.log(d);
    function pad(n, digits) {
        let s = "" + n;
        while (s.length < digits)  s = '0' + s;
        return s;
    }
    const out = [
            pad(d.getUTCFullYear(), 4), '-',
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

const gSocket = OpenSocket();

gSocket.onopen = function (e) {
  console.log("Connected to server socket");
};

gSocket.onmessage = SocketMessageHandler;

gSocket.onerror = function (e) {
   const m = "Cannot connect to Server: try reloading";
   console.log("ERROR: " + m);
   document.getElementById(STATUS_FIELD).innerHTML = m;
   tab.innerHTML = "ERROR: Cannot connect to Server: try reloading";
}

gSocket.onclose = function (e) {
    const m =  "Server connection lost: you must reload";
    console.log("ERROR: " + m);
    document.getElementById(STATUS_FIELD).innerHTML = m;
}

ShowTab(TAB_CONTROLLER);
for (let key in tabToDisplay) {
    UpdateSome(key);
}

UpdateDriverInfo();

const created = DateToString(new Date());

document.getElementById("timestamp").innerHTML = "" + created;

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


class Db(object):
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


# ======================================================================
# A few globals
# ======================================================================

DRIVER: Driver = None
CONTROLLER: Controller = None
PROTOCOL_NODESET: protocol_node.NodeSet = None
APPLICATION_NODESET: application_node.ApplicationNodeSet = None
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


def SendToSocket(mesg):
    # logging.error("Sending to socket: %d", len(SOCKETS))
    for s in SOCKETS:
        s.write_message(mesg)
    # logging.error("Sending to socket done: %d", len(SOCKETS))


class NodeUpdater(object):

    def __init__(self):
        self._nodes_to_update = set()
        self._update_driver = False
        timerThread = threading.Thread(target=self._refresh_thread)
        timerThread.daemon = True
        timerThread.start()

    def _refresh_thread(self):
        logging.warning("Refresher thread started")
        count = 0
        while True:
            if self._update_driver:
                SendToSocket("d:" + RenderDriver(DRIVER))
            if not APPLICATION_NODESET:
                continue
            for n in self._nodes_to_update:
                node = APPLICATION_NODESET.GetNode(n)
                SendToSocket("o%d:" % n + json.dumps(RenderNode(node, DB),
                                                     sort_keys=True, indent=4))
            self._update_driver = False
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

    def put(self, n, _ts, _key, _values):
        # SendToSocket("E:[%d] %s" % (n, "@NO EVENT@"))
        self._nodes_to_update.add(n)
        self._update_driver = True


def ControllerEventCallback(action, event):
    SendToSocket("S:" + event)
    SendToSocket("A:" + action)
    if event == EVENT_UPDATE_COMPLETE:
        SendToSocket("c:" + json.dumps(RenderController(CONTROLLER),
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
        args = {
            "css_path": OPTIONS.css_style_file,
            "title": "Web-Zwaver",
            "body": BODY,
            "script": SCRIPT,
        }
        self.write(HTML % args)
        self.finish()


def _MakeButton(action, param, label, cls=""):
    if cls:
        cls = "class='" + cls + "' "
    s = "<button onclick='%s(event)' %sdata-param='%s'>%s</button>"
    return s % (action, cls, param, label)


def _MakeNodeButton(node, action, label, cls=""):
    return _MakeButton("HandleUrl", "/node/%d/%s" % (node.n, action), label, cls)


def _MakeNodeButtonInput(node, action, label):
    return _MakeButton("HandleUrlInput", "/node/%d/%s" % (node.n, action), label)


def _MakeNodeRange(node: application_node.ApplicationNode, action, lo, hi):
    s = ("<input onchange='HandleChange(event)' data-param='/node/%d/%s/' class='multilevel' "
         "type=range min=%f max=%f value='%f'>")
    return s % (node.n, action, lo, hi, node.values.GetMultilevelSwitchLevel())


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


def ClassSpecificNodeButtons(node: application_node.ApplicationNode):
    out = []
    if node.values.HasCommandClass(z.SwitchBinary):
        out.append(_MakeNodeButton(node, "binary_switch/0", "Off"))
        out.append(_MakeNodeButton(node, "binary_switch/255", "On"))
    if node.values.HasCommandClass(z.SwitchMultilevel):
        out.append(_MakeNodeRange(node, "multilevel_switch", 0, 100)),
    if node.values.HasCommandClass(z.Meter):
        # reset
        pass
    return out


def MakeTableRowForNode(node: application_node.ApplicationNode, _is_failed):
    global DB
    readings = node.values.Sensors() + node.values.Meters() + node.values.MiscSensors()

    buttons = []
    if not node.IsSelf():
        buttons.append(_MakeNodeButton(node, "ping", "Ping"))
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
    last_contact = TimeFormat(pnode.last_contact)
    age = "never"
    if pnode.last_contact:
        age = "%dm ago" % ((time.time() - pnode.last_contact) / 60.0)
    return [
        "<tr>",
        "<td class=name>",
        _MakeButton(action, param, name, cls="details"),
        "</td>",
        "<td colspan=3 class=readings>%s</td>" % " ".join(
            RenderReadings(readings)),
        "</tr>",
        #
        "<tr>",
        "<td>" + " ".join(buttons) + "</td>",
        "<td class=no>node: %d</td>" % node.n,
        "<td class=state>%s (%s) [%s]</td>" % (last_contact, age, state),
        "<td class=product>%s (%s)</td>" % (pnode.device_description,
                                            pnode.device_type),
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


def RenderController(controller):
    out = {
        "controller_basics": "<pre>%s</pre>" % controller.StringBasic(),
        "controller_routes": "<pre>%s</pre>" % controller.StringRoutes(),
        "controller_apis": "<pre>%s</pre>" % controller.props.StringApis(),
    }
    return out


def RenderDriver(driver):
    return "<pre>" + str(driver) + "</pre>"


def DriverLogs(driver):
    out = []
    for t, sent, m, comment in driver._raw_history:
        t = TimeFormatMs(t)
        d = sent and "=>" or "<="
        m = zmessage.PrettifyRawMessage(m)
        out.append({"t": t, "c": comment, "d": d, "m": m})
    return out


def DriverSlow(driver):
    out = []
    for m in driver._history:
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


def DriverBad(driver):
    out = []
    for m in driver._history:
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
                SendToSocket("d:" + RenderDriver(DRIVER))
            elif cmd == "logs":
                SendToSocket("l:" + json.dumps(DriverLogs(DRIVER),
                                               sort_keys=True, indent=4))
            elif cmd == "slow":
                SendToSocket("b:" + json.dumps(DriverSlow(DRIVER),
                                               sort_keys=True, indent=4))
            elif cmd == "failed":
                SendToSocket("f:" + json.dumps(DriverBad(DRIVER),
                                               sort_keys=True, indent=4))

            elif cmd == "controller":
                SendToSocket("c:" + json.dumps(RenderController(CONTROLLER),
                                               sort_keys=True, indent=4))
            elif cmd == "node":
                num = int(token.pop(0))
                if num == 0:
                    logging.error("no current node")
                else:
                    node = APPLICATION_NODESET.GetNode(num)
                    SendToSocket("o%d:" % num + json.dumps(RenderNode(node, DB),
                                                           sort_keys=True, indent=4))
            else:
                logging.error("unknown command %s", token)
        except:
            logging.error("cannot processed: %s", path[0])
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
        self.finish()


def GetControls(node: application_node.ApplicationNode):
    return {
        "one_node_switch": node.values.HasCommandClass(z.SwitchBinary),
        "one_node_slide": node.values.HasCommandClass(z.SwitchMultilevel),
    }


def RenderAssociationGroup(node: application_node.ApplicationNode, no, group, name, info, lst):
    group_name = ""
    if name:
        group_name = name["name"]
    out = ["<tr>"
           "<th>", "Group %d %s [%d]:" % (
               no, group_name, group["count"]), "</th>",
           "<td>",
           ]
    for n in group["nodes"]:
        out += ["%d" % n,
                _MakeNodeButton(node, "association_remove/%d/%d" %
                                (no, n), "X", "remove"),
                "&nbsp;"]

    out += ["</td>",
            "<td>",
            _MakeNodeButtonInput(node, "association_add/%d/" % no, "Add Node"),
            "<input type=number min=0 max=232 value=0>",
            "</td>",
            "</tr>"]
    return "".join(out)


def RenderNodeCommandClasses(node: application_node.ApplicationNode):
    out = ["<table>"]
    for cls, name, version in sorted(node.values.CommandVersions()):
        out += ["<tr><td>%s [%d]</td><td>%d</td></tr>" % (name, cls, version)]
    out += ["</table>"]
    return out


def RenderNodeAssociations(node: application_node.ApplicationNode):
    out = [
        "<p>",
        "<table>",
    ]
    for no, group, info, lst, name in node.values.Associations():
        if group:
            out.append(RenderAssociationGroup(
                node, no, group, info, lst, name))
    out += ["</table>"]
    return out


def RenderNodeParameters(node: application_node.ApplicationNode):
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


def RenderNodeScenesOld(node: application_node.ApplicationNode):
    out = ["<table>"]
    for a, b, c in sorted(node.values.SceneActuatorConfiguration()):
        out += ["<tr> <td>%d</td> <td>%d</td> <td>%d</td></tr>" % (a, b, c)]
    out += ["</table>"]
    return out


def RenderNodeScenes(node: application_node.ApplicationNode):
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


def RenderMiscValues(node: application_node.ApplicationNode):
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


def RenderNode(node: application_node.ApplicationNode, db):
    readings = (RenderReadings(node.values.Sensors() +
                               node.values.Meters() +
                               node.values.MiscSensors()))
    out = {
        "one_node_name": db.GetNodeName(node.n),
        "one_node_switch_level": node.values.GetMultilevelSwitchLevel(),
        "one_node_controls": GetControls(node),
        "one_node_basics": "<pre>%s</pre>\n" % node.BasicString(),
        "one_node_classes": "\n".join(RenderNodeCommandClasses(node)),
        "one_node_associations": "\n".join(RenderNodeAssociations(node)),
        "one_node_values": "\n".join(RenderMiscValues(node)),
        "one_node_configurations": "\n".join(RenderNodeParameters(node)),
        "one_node_readings": "\n".join(readings),
        "one_node_scenes": "\n".join(RenderNodeScenes(node)),
    }

    return out


class NodeActionHandler(BaseHandler):
    """Single Node Actions"""

    def get(self, *path):
        global APPLICATION_NODESET, DB
        token = path[0].split("/")
        logging.error("NODE ACTION> %s", token)
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
            elif cmd == "refresh_scenes":
                node.RefreshAllSceneActuatorConfigurations()
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
            elif cmd == "change_scene":
                scene = int(token.pop(0))
                level = int(token.pop(0))
                delay = int(token.pop(0))
                extra = int(token.pop(0))
                node.SetSceneConfig(scene, delay, level, extra, True)
            elif cmd == "set_name" and token:
                print("TTTTTTTTTO: ", token)
                DB.SetNodeName(num, token.pop(0))
            elif cmd == "reset_meter":
                node.ResetMeter()
        except:
            logging.error("cannot processed: %s", path[0])
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
        self.finish()


def BalanceNodes(_m):
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
    # handles controller actions which will typically result in updates being send to the
    # websocket
    (r"/controller/(.+)", ControllerActionHandler, {}),
    (r"/node/(.+)", NodeActionHandler, {}),
    (r"/display/(.+)", DisplayHandler, {}),
    (r"/updates", EchoWebSocket, {}),
]


def _ProductSearchLink(prod_type, prod_id):
    return "http://www.google.com/search?q=site:products.z-wavealliance.org+0x%04x+0x%04x" % (prod_type, prod_id)


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


def main():
    global DRIVER, CONTROLLER, PROTOCOL_NODESET, APPLICATION_NODESET, DB
    # note: this makes sure we have at least one handler
    # logging.basicConfig(level=logging.WARNING)
    # logging.basicConfig(level=logging.ERROR)

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
        # debug=True,
        task_pool=multiprocessing.Pool(OPTIONS.tasks),
        # map static/xxx to Static/xxx
        static_path="Static/",
    )

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
