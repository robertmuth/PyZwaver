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
from pyzwaver.command import NodeDescription
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
<button onclick='HandleAction(event)' data-param='/controller/refresh'>
    Refresh</button>
&nbsp;
<button onclick='HandleAction(event)' data-param='/controller/soft_reset'>
    Soft Reset</button>
&nbsp;
<button onclick='HandleAction(event)' data-param='/controller/hard_reset'>
    Hard Reset</button>
</div>

<h2>Pairing</h2>

<button onclick='HandleAction(event)' data-param='/controller/add_node'>
    Add Node</button>
&nbsp;
<button onclick='HandleAction(event)' data-param='/controller/remove_node'>
    Remove Node</button>
&nbsp;
<button onclick='HandleAction(event)' data-param='/controller/add_controller_primary'>
    Add Primary Controller</button>
&nbsp;
<button onclick='HandleAction(event)' data-param='/controller/set_learn_mode'>
    Enter Learn Mode</button>
    
<h2>APIs</h2>
<div id=controller_apis></div>
    
</div>

<!-- ============================================================ -->
<div class=tab id=tab-all-nodes>

<table width=100%>
<tbody class='node_rows'>
<tr class='node_row'>
    <td class=node_actions valign='top'>
        <button class='node_name' onclick='HandleTabNode(event)' data-param='<CURRENT>'>name</button>    
       
       <p>
         <button onclick='HandleAction(event)' data-param='/node/<CURRENT>/ping'>Ping Node</button>
         &nbsp;
         <button class='node_switch_off' onclick='HandleAction(event)' 
                 data-param='/node/<CURRENT>/binary_switch/0'>Off</button>
         &nbsp;
         <button class='node_switch_on' onclick='HandleAction(event)' class='multilevel' 
                 data-param='/node/<CURRENT>/binary_switch/99'>On</button>
         &nbsp;
         <input class='node_slide' onchange='HandleAction(event)'  data-args='node_slide'
                data-param='/node/<CURRENT>/multilevel_switch/'  type=range min=0 max=100 value=0>
        </p>
    </td>

   <td class=node_info valign='top'>
       <div class=node_readings class=readings>READINGS</div>
       <p>
         <span class=node_no>node</span>
         <span class=node_last_contact>last contact</span>
         <span class=node_state>state</span>
         <span class=node_product>product</span>
       </p>
   </td>
</tr>
</tbody>

</table>
</div>

<!-- ============================================================ -->
<div class=tab id=tab-one-node>

<h2>Basics</h2>
<div class=node_basics></div>

<table width='100%'>
<tr>

<td width='45%' valign='top'><h2>Actions</h2>
<div class=node_actions>

  <button class='node_switch_off' onclick='HandleAction(event)' 
         data-param='/node/<CURRENT>/binary_switch/0'>Off</button>
  &nbsp;
  <button class='node_switch_on' onclick='HandleAction(event)' class='multilevel' 
          data-param='/node/<CURRENT>/binary_switch/99'>On</button>
  &nbsp;
  <input class='node_slide' onchange='HandleAction(event)' data-args='node_slide'
         data-param='/node/<CURRENT>/multilevel_switch/' type=range min=0 max=100 value=0>
 </td>

<td width='45%' valign='top'><h2>Readings</h2>
<div class=node_readings></div>
</td>

</tr>
</table>

<h2>Maintenance</h2>
<table width='100%' class=node_maintenance>
<tr>
<td width='45%' valign='top'>

<button onclick='HandleAction(event)' data-param='/node/<CURRENT>/ping'>
    Ping Node</button>
&nbsp;
<button class=node_documentation onclick='HandleUrl(event)' data-param=''>
    Search Documentation</button>
<p>
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
<button class='node_scene_refresh' onclick='HandleAction(event)' data-param='/node/<CURRENT>/refresh_scenes'>
    Probe Scenes</button>
&nbsp;

</td>


    
<td width='45%' valign='top'>
<button onclick='HandleAction(event)' 
        data-param='/node/<CURRENT>/set_name/'
        data-args='node_name'>
    Change Node Name</button>
    <input type=text class=node_name>
<p> 

<button onclick='HandleAction(event)' 
        data-param='/node/<CURRENT>/change_parameter/'
        data-args='config_num,config_size,config_value'>
    Change Config Param</button>    
no <input class=config_num type='number' value=0 min=1 max=232 style='width: 3em'>
size <select class=config_size name='size'>
<option value='1'>1</option>
<option value='2'>2</option>
<option value='4'>4</option>
</select>
value <input class=config_value type='number' value=0 style='width: 7em'>

<p>

<button onclick='HandleAction(event)' 
        data-param='/node/<CURRENT>/change_scene/'
        data-args='scene_num,scene_level,scene_delay,scene_extra'>
    Change Scene Config</button>    
no <input class=scene_num type='number'  value=1 min=1 max=255 style='width: 3em'>
level <input class=scene_level type='number' value=0 min=0 max=255 style='width: 3em'>
delay <input class=scene_delay type='number' value=0 min=0 max=255 style='width: 3em'>

<select class=scene_extra name='extra'>
<option value='128'>on</option>
<option value='0'>off</option>
</select>

<p>
   
Association group <input class=assoc_group type='number' name='level' value=1 min=0 max=255 style='width: 3em'>
node <input class=assoc_node type='number' name='level' value=0 min=0 max=255 style='width: 3em'>
<button onclick='HandleAction(event)' 
        data-param='/node/<CURRENT>/association_remove/'
        data-args='assoc_group,assoc_node'>
    Remove</button>  
<button onclick='HandleAction(event)' 
        data-param='/node/<CURRENT>/association_add/'
        data-args='assoc_group,assoc_node'>
    Add</button> 
</td>
</tr>

</table>


<h2>Associations</h2>
<div class=node_associations></div>

<h2>Values</h2>
<div class=node_values></div>

<table width='100%'>

<tr>
<td width='33%' valign='top'>
<h2>Command Classes</h2>
<div class=node_classes></div>
</td>

<td width='33%' valign='top'>
<h2>Configuration</h2>
<div class=node_configurations></div>
</td>

<td width='33%' valign='top'>
<h2>Scenes</h2>
<div class=node_scenes></div>
</td>

</tr>
</table>
 
</div>

<!-- ============================================================ -->
<div class=tab id=tab-logs>
    <p>
    <input type=search 
           oninput='InstallLogFilter(event)' 
           id=log_filter_regexp 
           placeholder="Regexp Filter"/>
    </p>
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

# language="JShell snippet"
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
// t: timestamp
// c: completion status
// d: direction
// m: message
const listLog = new List('driverlog', {valueNames: [ 't', 'c', 'd', 'm' ]});
const listSlow = new List('driverslow', {valueNames: [ 'd', 't', 'm' ]});
const listFailed = new List('driverfailed', {valueNames: [ 'd', 't', 'm' ]});

function InstallLogFilter(ev) {
    if (ev) {
        ev.preventDefault();
        ev.stopPropagation();
    }
    let text = document.getElementById('log_filter_regexp').value;
    listLog.filter();
    console.log(`Filter is: /${text}/`);
    if (text) {
        listLog.filter(
            function (item) {
                return item.values().m.match(new RegExp(text)); 
        });
    }
}

function OpenSocket() {
    const loc = window.location;
    const prefix = loc.protocol === 'https:' ? 'wss://' : 'ws://';
    return new WebSocket(prefix + loc.host + "/updates");
}

function ShowHideControls(root, controls) {
    for (let key in controls) {
        let e = root.getElementsByClassName(key);
        if (e.length > 0) {
            let val = controls[key];
            //console.log(`${e[0]}: ${key} -> ${val} [${e[0].dataset.param}]`);
            e[0].hidden = ! val;
        }
    }
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
         InstallLogFilter(null);
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
         const values = JSON.parse(val);
         const rows = document.getElementsByClassName("node_row");
         console.log(`found ${rows.length} rows`);
         for (let i = 0; i < rows.length; ++i) {
             const root= rows[i];
             const data = values[i + 1];
             if (!data) {
                 root.hidden = true;
                 continue;
             }
             root.hidden = false;
             root.getElementsByClassName("node_name")[0].innerHTML = data.name;
             root.getElementsByClassName("node_slide")[0].value = data.switch_level;
             root.getElementsByClassName("node_readings")[0].innerHTML = data.readings;
             root.getElementsByClassName("node_last_contact")[0].innerHTML = data.last_contact;
             root.getElementsByClassName("node_product")[0].innerHTML = data.product;
             root.getElementsByClassName("node_state")[0].innerHTML = data.state;
             root.getElementsByClassName("node_no")[0].innerHTML = data.no;
             ShowHideControls(root, data.controls);
         }
         //document.getElementById(TAB_ALL_NODES).innerHTML = val;
    } else if (tag[0] == "o") {
        // ONE-NODE
        const values = JSON.parse(val);
        const node = tag.slice(1);
        if (node == currentNode) {
            const root = document.getElementById(TAB_ONE_NODE);
            root.getElementsByClassName("node_basics")[0].innerHTML = values.basics;
            root.getElementsByClassName("node_classes")[0].innerHTML = values.classes;
            root.getElementsByClassName("node_associations")[0].innerHTML = values.associations;
            root.getElementsByClassName("node_values")[0].innerHTML = values.values;
            root.getElementsByClassName("node_configurations")[0].innerHTML = values.configurations;
            root.getElementsByClassName("node_readings")[0].innerHTML = values.readings;
            root.getElementsByClassName("node_scenes")[0].innerHTML = values.scenes;
            
            root.getElementsByClassName("node_documentation")[0].dataset.param = values.link;
            root.getElementsByClassName("node_name")[0].value = values.name;
            root.getElementsByClassName("node_slide")[0].value = values.switch_level;
            ShowHideControls(root, values.controls);
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
   UpdateSome(id);
   UpdateDriver();
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
    const root = ev.target.parentNode;
    // console.log(`${root}: ${ev.target.dataset.args}`)
    let args= [];
    const elem_list = ev.target.dataset.args;
    if (elem_list) {
        for (let elem of elem_list.split(',')) {
            args.push(root.getElementsByClassName(elem)[0].value);
        }
    }
    console.log("HandleAction: " + param + ": " + args);
    RequestActionURL(param, args);
}


function HandleUrl(ev) {
    window.location = ev.target.dataset.param;
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
    window.history.pushState({}, "", "#" + param);
}

function HandleTabNode(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const param = ev.target.dataset.param;
    console.log("HandleTabNode: " + param + ": " + ev.target);
    currentNode = param;
    ShowTab(TAB_ONE_NODE);
    window.history.pushState({}, "", "#tab-one-node/" + param);
}

function UpdateSome(tab) {
    RequestURL(tabToDisplay[tab]());
}

function UpdateDriver() {
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
  console.log(`Hash: [${tokens.length}] ${tokens}`);
  if (tokens.length > 1) {
     currentNode = tokens[1];
  }
  ShowTab(tokens[0]);
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
  
  // Replicate node row in node overview page
  const node_row_template = document.getElementsByClassName("node_rows")[0];
  const table = node_row_template.parentNode;
  const text = node_row_template.innerHTML;
  const all = [];
  for (let i = 1 ; i < 256; ++i) {
    all.push(text.replace(new RegExp("<CURRENT>", "g"), "" + i));
  }
  table.innerHTML = all.join("");
  
  const created = DateToString(new Date());
  document.getElementById("timestamp").innerHTML = "" + created;
  
  console.log("on load finished");
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


def SendToSocket(mesg: str):
    # logging.error("Sending to socket: %d", len(SOCKETS))
    for s in SOCKETS:
        s.write_message(mesg)
    # logging.error("Sending to socket done: %d", len(SOCKETS))


def SendToSocketJson(prefix: str, data: object):
    SendToSocket(prefix + json.dumps(data, sort_keys=True, indent=4))


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
            if self._update_driver or DRIVER.HasInflight():
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
                    node: application_node.ApplicationNode = APPLICATION_NODESET.GetNode(n)
                    if node.state < application_node.NODE_STATE_DISCOVERED:
                        PROTOCOL_NODESET.Ping(n, 3, False)
                        time.sleep(0.5)
                    elif node.state < application_node.NODE_STATE_INTERVIEWED:
                        node.RefreshStaticValues()
            count += 1
            time.sleep(1.0)

    def put(self, n, _ts, _key, _values):
        #print ("got event ", n, _key, _values)
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


def RenderNodes(application_nodes, controller, db):
    out = {}
    nodes = controller.nodes
    failed = controller.failed_nodes
    for node in sorted(application_nodes.nodes.values()):
        if node.n not in nodes:
            continue
        out[node.n] = RenderNodeBrief(node, db, node.n in failed)
    return out


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


def GetControls(node: application_node.ApplicationNode):
    is_switch = node.values.HasCommandClass(z.SwitchBinary)
    out = {
        "node_switch_on": is_switch,
        "node_switch_off": is_switch,
        "node_slide": node.values.HasCommandClass(z.SwitchMultilevel),
        "node_scene_refresh": node.values.HasCommandClass(z.SceneActuatorConf),
    }
    return out


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
                "&nbsp;"]

    out += ["</td>",
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


def _ProductLink(_manu_id, prod_type, prod_id):
    return "http://www.google.com/search?q=site:products.z-wavealliance.org+0x%04x+0x%04x" % (prod_type, prod_id)


def RenderNodeBrief(node: application_node.ApplicationNode, db, _is_failed):
    readings = (RenderReadings(node.values.Sensors() +
                               node.values.Meters() +
                               node.values.MiscSensors()))
    state = node.state[2:]
    # TODO
    #if pnode.failed:
    #    state = "FAILED"
    age = "never"
    if node.last_contact:
        age = "%dm ago" % ((time.time() - node.last_contact) / 60.0)

    device_type = node.values.DeviceType()
    description = NodeDescription(device_type)

    out = {
        "name": db.GetNodeName(node.n),
        "link": _ProductLink(*node.values.ProductInfo()),
        "switch_level": node.values.GetMultilevelSwitchLevel(),
        "controls": GetControls(node),
        "basics": "<pre>%s</pre>\n" % node.BasicString(),
        "readings": "\n".join(readings),
        "no": node.n,
        "state": state,
        "last_contact": "(%s) [%s]" % (TimeFormat(node.last_contact), age),
        "product": "%s (%s)" % (description, device_type),
    }

    return out


def RenderNode(node: application_node.ApplicationNode, db):
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
                node._nodeset.Ping(3, True)
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
                DB.SetNodeName(num, token.pop(0))
            elif cmd == "reset_meter":
                node.ResetMeter()
        except:
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
    def get(self, *path):
        token = path[0].split("/")
        logging.warning("JSON ACTION> %s", token)
        cmd = token.pop(0)
        out = None
        try:
            if cmd == "nodes":
                out = RenderNodes(APPLICATION_NODESET, CONTROLLER, DB)
            elif cmd == "driver":
                out = RenderDriver(DRIVER)
            elif cmd == "logs":
                out = DriverLogs(DRIVER)
            elif cmd == "slow":
                out = DriverSlow(DRIVER)
            elif cmd == "failed":
                out = DriverBad(DRIVER)
            elif cmd == "controller":
                out = RenderController(CONTROLLER)
            elif cmd == "node":
                num = int(token.pop(0))
                if num == 0:
                    logging.error("no current node")
                else:
                    node = APPLICATION_NODESET.GetNode(num)
                    out = RenderNode(node, DB)
            else:
                logging.error("unknown command %s", token)
            self.write(json.dumps(out, sort_keys=True, indent=4))
        except:
            logging.error("cannot processed: %s", path[0])
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
        self.finish()

    @tornado.web.asynchronous
    def options(self):
        # no body
        self.set_status(204)
        self.finish()


class DisplayHandler(BaseHandler):
    """Misc Display Handlers"""

    @tornado.web.asynchronous
    def get(self, *path):
        token = path[0].split("/")
        logging.warning("DISPLAY ACTION> %s", token)
        cmd = token.pop(0)
        try:
            if cmd == "nodes":
                SendToSocketJson("a:", RenderNodes(APPLICATION_NODESET, CONTROLLER, DB))
            elif cmd == "driver":
                SendToSocket("d:" + RenderDriver(DRIVER))
            elif cmd == "logs":
                SendToSocketJson("l:", DriverLogs(DRIVER))
            elif cmd == "slow":
                SendToSocketJson("b:", DriverSlow(DRIVER))
            elif cmd == "failed":
                SendToSocketJson("f:", DriverBad(DRIVER))
            elif cmd == "controller":
                SendToSocketJson("c:", RenderController(CONTROLLER))
            elif cmd == "node":
                num = int(token.pop(0))
                if num == 0:
                    logging.error("no current node")
                else:
                    node = APPLICATION_NODESET.GetNode(num)
                    SendToSocketJson("o%d:" % num, RenderNode(node, DB))
            else:
                logging.error("unknown command %s", token)
        except Exception as e:
            logging.error("cannot processed: %s", path[0])
            print("-" * 60)
            traceback.print_exc(file=sys.stdout)
            print("-" * 60)
        self.finish()


HANDLERS = [
    ("/", MainHandler, {}),

    # handles controller actions which will typically result in
    # updates being send to the websocket(s)
    (r"/controller/(.+)", ControllerActionHandler, {}),
    # handles node actions which will typically result in
    # updates being send to the websocket(s)
    (r"/node/(.+)", NodeActionHandler, {}),
    # Request updates being send to the websocket(s)
    (r"/display/(.+)", DisplayHandler, {}),
    # for debugging
    ("/json/(.+)", JsonHandler, {}),
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
    #logger.setLevel(logging.WARNING)
    #logger.setLevel(logging.ERROR)
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
    PROTOCOL_NODESET = protocol_node.NodeSet(DRIVER)
    APPLICATION_NODESET = application_node.ApplicationNodeSet(PROTOCOL_NODESET, CONTROLLER.GetNodeId())

    cp = CONTROLLER.props.product
    APPLICATION_NODESET.put(
        CONTROLLER.GetNodeId(),
        time.time(),
        z.ManufacturerSpecific_Report,
        {'manufacturer': cp[0], 'type': cp[1], 'product': cp[2]})
    PROTOCOL_NODESET.AddListener(APPLICATION_NODESET)
    # The updater will do the initial pings of the nodes
    PROTOCOL_NODESET.AddListener(NodeUpdater())
    logging.warning("listening on port %d", OPTIONS.port)
    application.listen(OPTIONS.port)
    tornado.ioloop.IOLoop.instance().start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
