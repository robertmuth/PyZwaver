"use strict";
// ============================================================
// The JS part of this demo is intentionally kept at a minimum.
// Whenever possible work his shifted to Python code.
// ============================================================

// ============================================================
// Constants and Globals
// ============================================================
// Node that is currently shown in 'tab-one-node'
var currentNode = "0";

const gDebug = 0;
// "enums" for tabs
const TAB_CONTROLLER = "tab-controller";
const TAB_ALL_NODES = "tab-all-nodes";
const TAB_ONE_NODE = "tab-one-node";
const TAB_LOGS = "tab-logs";
const TAB_SLOW = "tab-slow";
const TAB_FAILED = "tab-failed";

const STATUS_FIELD = "status";

// multichannel device a shown as 1 + number_of_channels nodes
const MAX_NODE_ROWS = 500;

// Is there a literal notation for this?
const tabToDisplay = {
    [TAB_CONTROLLER]: function () { return "/display/CONTROLLER"; },
    [TAB_ALL_NODES]: function () { return "/display/ALL_NODES"; },
    [TAB_ONE_NODE]: function () { return "/display/ONE_NODE/" + currentNode; },
    [TAB_LOGS]: function () { return "/display/LOGS"; },
    [TAB_SLOW]: function () { return "/display/BAD"; },
    [TAB_FAILED]: function () { return "/display/FAILED"; },
};

let gEventHistory = ["", "", "", "", "", ""];

//  List visualization using the http://listjs.com/
// t: timestamp
// c: completion status
// d: direction
// m: message
let gListLog = null;
let gListSlow = null;
let gListFailed = null

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
        while (s.length < digits) s = '0' + s;
        return s;
    }
    const out = [
        pad(d.getUTCFullYear(), 4), '-',
        pad(d.getUTCMonth() + 1, 2), '-',
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
            e[0].hidden = !val;
        }
    }
}

function SetInnerHtmlForClass(elem, cls, html) {
    elem.getElementsByClassName(cls)[0].innerHTML = html;
}

function SetInnerHtmlForId(elem, id, html) {
    elem.getElementById(id).innerHTML = html;
}

function RequestURL(url) {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.send();
}

function RequestRefresh(component) {
    RequestURL(tabToDisplay[component]());
    // always update the drive too
    RequestURL("/display/DRIVER");
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
        if (element.dataset.no !== undefined) return element.dataset.no;
    }
    return currentNode;
}

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

// ============================================================
// Updaters
// ============================================================

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
    SetInnerHtmlForClass(row, "node_values", data.values);
    SetInnerHtmlForClass(row, "node_configurations", data.configurations);
    SetInnerHtmlForClass(row, "node_readings", data.readings);
    SetInnerHtmlForClass(row, "node_scenes", data.scenes);
    row.getElementsByClassName("node_name")[0].value = data.name;
    row.getElementsByClassName("node_documentation")[0].dataset.url = data.link;
    row.getElementsByClassName("node_slide")[0].value = data.switch_level;
    ShowHideControls(row, data.controls);
}

const SocketHandlerDispatch = {
    ACTION: function (val) {
        SetInnerHtmlForId(document, "activity", val);
    },
    STATUS: function (val) {
        console.log(val);
        SetInnerHtmlForId(document, STATUS_FIELD, val);
    },
    EVENT: function (val) {
        gEventHistory.push(val);
        gEventHistory.shift();
        SetInnerHtmlForId(document, "history", gEventHistory.join("\\n"));
    },
    CONTROLLER: function (val) {
        const values = JSON.parse(val);
        SetInnerHtmlForId(document, 'controller_basics', values.controller_basics);
        SetInnerHtmlForId(document, 'controller_routes', values.controller_routes);
        SetInnerHtmlForId(document, 'controller_apis', values.controller_apis);
    },
    LOGS: function (val) {
        const values = JSON.parse(val);
        gListLog.clear();
        gListLog.add(values);
        InstallLogFilter(null);
    },
    BAD: function (val) {
        const values = JSON.parse(val);
        gListSlow.clear();
        gListSlow.add(values);
    },
    FAILED: function (val) {
        const values = JSON.parse(val);
        gListFailed.clear();
        gListFailed.add(values);
    },
    ALL_NODES: function (val) {
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
    ONE_NODE: function (val) {
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
    DRIVER: function (val) {
        SetInnerHtmlForId(document, "driver", val);
    },
};

// Redraws work by triggering event in the Python code that will result
// in HTML fragments being sent to socket.
function SocketMessageHandler(e) {
    const colon = e.data.indexOf(":");
    const tag = e.data.slice(0, colon);
    const val = e.data.slice(colon + 1);
    if (gDebug) console.log("socket: " + tag);
    console.log(`socket: [${tag}]  ${val.substr(0, 40)}`);
    SocketHandlerDispatch[tag](val);
}

// ============================================================
// Button Click Etc Handlers
// ============================================================

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
    const param = ev.target.dataset.param.replace("<CURRENT>", GetCurrNode(ev.target));
    const root = ev.target.parentNode;
    let args = [];
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
    let state = "#" + param;
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

window.onload = function () {

    // Replicate node row in node overview page
    const node_row_template = document.getElementsByClassName("node_rows")[0];
    const table = node_row_template.parentNode;
    const text = node_row_template.innerHTML;
    const all = [];
    for (let i = 1; i < MAX_NODE_ROWS; ++i) {
        all.push(text)
    }
    table.innerHTML = all.join("");

    const created = DateToString(new Date());
    SetInnerHtmlForId(document, "timestamp", "" + created);

    gListLog = new List("driverlog", { valueNames: ['t', 'c', 'd', 'm'] });
    gListSlow = new List("driverslow", { valueNames: ['d', 't', 'm'] });
    gListFailed = new List("driverfailed", { valueNames: ['d', 't', 'm'] });

    const gSocket = OpenSocket();
    gSocket.onopen = function (e) {
        console.log("Connected to server socket");
    };

    gSocket.onmessage = SocketMessageHandler;

    gSocket.onerror = function (e) {
        const m = "Cannot connect to Server: try reloading";
        console.log("ERROR: " + m);
        SetInnerHtmlForId(document, STATUS_FIELD, m);
        tab.innerHTML = "ERROR: Cannot connect to Server: try reloading";
    }

    gSocket.onclose = function (e) {
        const m = "Server connection lost: you must reload";
        console.log("ERROR: " + m);
        SetInnerHtmlForId(document, STATUS_FIELD, m);
    }

    // delay this until the socket has been setup since it will trigger updates
    ProcessUrlHash();

    console.log("on load finished");
};

// we use window.parent to make this work even from within an iframe
window.parent.onpopstate = function (event) {
    ProcessUrlHash();
};

