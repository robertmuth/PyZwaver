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
Basic mqtt proxy for pyzwaver

topic format for outgoing messages is
zwave_out/<home-id>/<node-number>/<command> json-payload

topic format for incoming messages is
zwave_in/<home-id>/<node-number>/<command> json-payload

to send a command to the proxy use something like:
mosquitto_pub -h <mqtt-broker> -t zwave_out/<home-id>/<node-num>/Basic_Set -m '{"level": 255}'

"""

# python import
import datetime
import logging
import argparse
import sys
import time
import json

import paho.mqtt.client as mqtt

from pyzwaver.controller import Controller
from pyzwaver.driver import Driver, MakeSerialDevice
from pyzwaver.command_translator import CommandTranslator
from pyzwaver import command
from pyzwaver.node import Nodeset, XMIT_OPTIONS
from pyzwaver.zwave import STRING_TO_SUBCMD
from pyzwaver.zmessage import NodePriorityHi


class MyFormatter(logging.Formatter):
    """
    Nicer logging format
    """

    def __init__(self):
        super(MyFormatter, self).__init__()

    TIME_FMT = '%Y-%m-%d %H:%M:%S.%f'

    def format(self, record):
        return "%s%s %s:%s:%d %s" % (
            record.levelname[0],
            datetime.datetime.fromtimestamp(record.created).strftime(MyFormatter.TIME_FMT)[:-3],
            record.threadName,
            record.filename,
            record.lineno,
            record.msg % record.args)


# json does not by default handle bytes, set
class PythonObjectEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(set)
        elif isinstance(obj, bytes):
            return "".join(map(chr, obj))
        return json.JSONEncoder.default(self, obj)


class EventListener(object):

    def __init__(self, home_id, mqtt_client: mqtt.Client):
        self._home_id = home_id
        self._mqtt_client = mqtt_client

    def put(self, n, _ts, key, values):
        if key[0] is None or command.IsCustom(key):
            return
        name = command.StringifyCommand(key)
        # print("@@@IN", name, values)
        self._mqtt_client.publish(
            "zwave_in/%d/%d/%s" % (self._home_id, n, name),
            json.dumps(values, cls=PythonObjectEncoder))


def main():
    global driver, controller, translator, nodeset

    parser = argparse.ArgumentParser(description='Process some integers.')

    parser.add_argument(
        '--serial_port',
        type=str,
        default="/dev/ttyUSB0",
        help='The USB serial device representing the Z-Wave controller stick. ' +
        'Common settings are: dev/ttyUSB0, dev/ttyACM0')
    parser.add_argument('--mqtt_broker_host', type=str,
                        default="localhost",
                        help='mqtt broker host')
    parser.add_argument('--mqtt_broker_port', type=int,
                        default=1883,
                        help='mqtt broker port')
    parser.add_argument('--verbosity', type=int,
                        default=30,  # = logging.WARNING
                        help='Lower numbers mean more verbosity')

    args = parser.parse_args()
    # note: this makes sure we have at least one handler
    logging.basicConfig(level=args.verbosity)
    logger = logging.getLogger()
    logger.setLevel(args.verbosity)
    for h in logger.handlers:
        h.setFormatter(MyFormatter())

    logging.warning("opening serial: [%s]", args.serial_port)
    device = MakeSerialDevice(args.serial_port)

    driver = Driver(device)

    logging.warning("controller initializing")
    controller = Controller(driver, pairing_timeout_secs=60)
    controller.Initialize()
    controller.WaitUntilInitialized()
    controller.UpdateRoutingInfo()
    time.sleep(2)
    logging.warning("controller initialized:\n" + str(controller))

    translator = CommandTranslator(driver)
    nodeset = Nodeset(translator, controller.GetNodeId())

    def on_connect(client, _userdata, _rc, _dummy):
        logging.warning("Initialized MQTT client")
        logging.warning("Pinging %d nodes", len(controller.nodes))
        for n in controller.nodes:
            translator.Ping(n, 5, False, "initial")
            time.sleep(0.5)
            client.subscribe("zwave_out/%d/#" % controller.props.home_id)

    def on_message(client, _userdata, msg):
        tokens = msg.topic.split("/")
        key_int = STRING_TO_SUBCMD.get(tokens[3])
        if key_int is None:
            logging.error("unknown command: %s", tokens[3])
        key = ((key_int >> 8) & 255, key_int & 255)
        n = int(tokens[2])
        values = json.loads(msg.payload)
        logging.warning(
            "command received: %d [%s] %s",
            n,
            tokens[3],
            msg.payload)
        translator.SendCommand(n, key, values, NodePriorityHi(n), XMIT_OPTIONS)
        # print(n, key, data)

    logging.info("Initializing MQTT client")
    client = mqtt.Client("zwave-client")
    client.on_connect = on_connect
    client.on_message = on_message

    translator.AddListener(EventListener(controller.props.home_id, client))
    client.connect(
        args.mqtt_broker_host,
        port=args.mqtt_broker_port,
        keepalive=60)
    client.loop_forever()

    driver.Terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
