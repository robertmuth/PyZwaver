"use strict";
// ============================================================
// The JS part of this demo is intentionally kept at a minimum.
// Whenever possible work his shifted to Python code.
// ============================================================

// ============================================================
// Helpers
// ============================================================

function OpenSocket() {
    const loc = window.location;
    const prefix = loc.protocol === 'https:' ? 'wss://' : 'ws://';
    return new WebSocket(prefix + loc.host + "/updates");
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

function SetInnerHtmlForClass(elem, cls, html) {
     elem.getElementsByClassName(cls)[0].innerHTML = html;
}

// ============================================================
// Constants and Globals
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
let gListLog = null;
let gListSlow = null;
let gListFailed = null


function InstallLogFilter(ev) {
    if (ev) {
        ev.preventDefault();
        ev.stopPropagation();
    }
    let text = document.getElementById('log_filter_regexp').value;
    gListLog.filter();
    console.log(`Filter is: /${text}/`);
    if (text) {
        gListLog.filter(
            function (item) {
                return item.values().m.match(new RegExp(text));
        });
    }
}



function UpdateNodeRow(row, data) {
    row.dataset.no = data.no;
    row.getElementsByClassName("node_slide")[0].value = data.switch_level;
    SetInnerHtmlForClass(row, "node_name", data.name);
    SetInnerHtmlForClass(row, "node_readings", data.readings);
    SetInnerHtmlForClass(row, "node_last_contact", data.last_contact);
    SetInnerHtmlForClass(row, "node_product", data.product);
    SetInnerHtmlForClass(row, "node_state", data.state);
    SetInnerHtmlForClass(row, "node_no", data.no);
    ShowHideControls(row, data.controls);
}

function UpdateNodeDetails(row, data) {
    SetInnerHtmlForClass(row, "node_basics", data.basics);
    SetInnerHtmlForClass(row, "node_classes", data.classes);
    SetInnerHtmlForClass(row, "node_associations", data.associations);
    SetInnerHtmlForClass(row, "node_data", data.data);
    SetInnerHtmlForClass(row, "node_configurations", data.configurations);
    SetInnerHtmlForClass(row, "node_readings", data.readings);
    SetInnerHtmlForClass(row, "node_scenes", data.scenes);
    row.getElementsByClassName("node_name")[0].value = values.name;
    row.getElementsByClassName("node_documentation")[0].set.param = data.link;
    row.getElementsByClassName("node_slide")[0].value = data.switch_level;
    ShowHideControls(row, data.controls);
}


const SocketHandlerDispatch = {
  ACTION: function(val) {
      document.getElementById(ACTIVITY_FIELD).innerHTML = val;
  },
  STATUS: function(val) {
      console.log(val);
      document.getElementById(STATUS_FIELD).innerHTML = val;
  },
  EVENT: function(val) {
      gEventHistory.push(val);
      gEventHistory.shift();
      document.getElementById(HISTORY_FIELD).innerHTML = gEventHistory.join("\\n");
  },
  CONTROLLER: function(val) {
      const values = JSON.parse(val);
      document.getElementById('controller_basics').innerHTML =
          values.controller_basics;
      document.getElementById('controller_routes').innerHTML =
          values.controller_routes;
      document.getElementById('controller_apis').innerHTML =
           values.controller_apis;
  },
  LOGS: function(val) {
      const values = JSON.parse(val);
      gListLog.clear();
      gListLog.add(values);
      InstallLogFilter(null);
  },
  BAD: function(val) {
      const values = JSON.parse(val);
      gListSlow.clear();
      gListSlow.add(values);
  },
  FAILED: function(val) {
      const values = JSON.parse(val);
      gListFailed.clear();
      gListFailed.add(values);
  },
  ALL_NODES: function(val) {
      const values = JSON.parse(val);
      const rows = document.getElementsByClassName("node_row");
      console.log(`found ${rows.length} rows`);
      for (let i = 0; i < values.length; ++i) {
          rows[i].hidden = false;
          UpdateNodeRow(rows[i], values[i]);
      }
      for (let i = values.length; i < rows.length; ++i) {
          rows[i].hidden = true;
      }
  },
  ONE_NODE: function(val) {
      const colon = val.indexOf(":");
      const node = val.slice(0, colon);
      const values = JSON.parse(val.slice(colon + 1));
      if (node == currentNode) {
          UpdateNodeDetails(document.getElementById(TAB_ONE_NODE), values);
      }
      const rows = document.getElementsByClassName("node_row");
      for (let i = 0; i < rows.length; ++i) {
            if (rows[i].dataset.no == node) {
                UpdateNodeRow(rows[i], values);
                break;
            }
      }
  },
  DRIVER: function(tag, val) {
      document.getElementById(DRIVE_FIELD).innerHTML = val;
  },
};

// Redraws work by triggering event in the Python code that will result
// in HTML fragments being sent to socket.
function SocketMessageHandler(e) {
    const colon = e.data.indexOf(":");
    const tag = e.data.slice(0, colon);
    const val = e.data.slice(colon + 1);
    if (gDebug) console.log("socket: " + tag);
    console.log("socket: " + tag);
    SocketHandlerDispatch[tag](val);
}

function RequestRefresh(component) {
    RequestURL(tabToDisplay[component]());
    // always update the drive too
    RequestURL("/display/driver");
}

// Show one tab while hiding the others.
function ShowTab(id) {
   const tabs = document.getElementsByClassName("tab");
    for (let i = 0; i < tabs.length; i++) {
        tabs[i].style.display = "none";
   }
   document.getElementById(id).style.display = "block";
   RequestRefresh(id);
}

function GetCurrNode(element) {
    for (; element != document.body; element = element.parentNode) {
        if ( element.dataset.no !== undefined) return element.dataset.no;
    }
    return currentNode;
}

// ============================================================
// Button Click Etc Handlers
// ============================================================
function RequestURL(url) {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.send();
}

// This will may trigger refreshes via the websocket
function RequestActionURL(param, args) {
    const base = "//" + window.location.host + param;
    RequestURL(base + args.join("/"));
}

// For most button clicks - send a message to the server.
// The server will send back updates via the WebSocket
function HandleAction(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const param = ev.target.dataset.param.replace("<CURRENT>",  GetCurrNode(ev.target));
    const root = ev.target.parentNode;
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
    window.location = ev.target.dataset.url;
}

function HandleUrlInput(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const param = ev.target.dataset.param.replace("<CURRENT>", currentNode);
    const input_elem = ev.target.parentElement.getElementsByTagName("input")[0];
    console.log("HandleUrl: " + param + ": " + input_elem.value + " " + ev.target);
    RequestActionURL(param, [input_elem.value]);
}

// For switching Tabs
function HandleTab(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const param = ev.target.dataset.tab;
    let state =  "#" + param;
    if (param == TAB_ONE_NODE) {
      currentNode = GetCurrNode(ev.target);
      state += `/${currentNode}`;
    }
    console.log("HandleTab: " + param + ": " + ev.target);
    ShowTab(param);
    window.history.pushState({}, "", state);
}

// ============================================================
// Initialization
// ============================================================
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

// multichannel device a shown as 1 + number_of_channels nodes
const MAX_NODE_ROWS = 500;

window.onload = function () {
  ProcessUrlHash();

  // Replicate node row in node overview page
  const node_row_template = document.getElementsByClassName("node_rows")[0];
  const table = node_row_template.parentNode;
  const text = node_row_template.innerHTML;
  const all = [];
  for (let i = 1 ; i < MAX_NODE_ROWS; ++i) {
    all.push(text)
  }
  table.innerHTML = all.join("");

  const created = DateToString(new Date());
  document.getElementById("timestamp").innerHTML = "" + created;

  gListLog = new List('driverlog', {valueNames: [ 't', 'c', 'd', 'm' ]});
  gListSlow = new List('driverslow', {valueNames: [ 'd', 't', 'm' ]});
  gListFailed = new List('driverfailed', {valueNames: [ 'd', 't', 'm' ]});
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
