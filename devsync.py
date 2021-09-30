import os
import json
import paho.mqtt.client as mqtt

from secrets import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, MQTT_CLIENT

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    global time_connected

    print('Connected with result code '+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    
    # figure out tasmota devices in a device group
    client.subscribe('stat/+/LOGGING')
    client.subscribe('stat/+/RESULT')
    client.publish('cmnd/tasmotas/DevGroupStatus1', payload='', retain=False)
    client.publish('cmnd/tasmotas/DevGroupStatus2', payload='', retain=False)
    client.publish('cmnd/tasmotas/DevGroupStatus3', payload='', retain=False)
    client.publish('cmnd/tasmotas/DevGroupStatus4', payload='', retain=False)

    # figure out z2m devices in a device group
    client.subscribe('zigbee2mqtt/bridge/devices')

tas_groups = {}
tas_devices = []

zig_groups = {}
zig_devices = []

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global tas_groups
    global tas_devices
    global zig_groups
    global zig_devices

    payload_str = str(msg.payload.decode("utf-8"))
    
    split_topic = msg.topic.split('/')
    if split_topic[1][0:7] == 'tasmota':
        prefix, device, topic = split_topic
        if topic == 'RESULT':
            payload_dict = json.loads(msg.payload)
            if 'DevGroupStatus' in payload_dict:
                print(device, payload_str)

                if payload_dict['DevGroupStatus']['GroupName'] in tas_groups:
                    tas_groups[payload_dict['DevGroupStatus']['GroupName']].append((device, payload_dict['DevGroupStatus']['Index']))
                else:
                    tas_groups[payload_dict['DevGroupStatus']['GroupName']] = [(device, payload_dict['DevGroupStatus']['Index'])]

                if device not in tas_devices:
                    tas_devices.append(device)
                    client.publish('cmnd/%s/mqttlog' % device, payload='4', retain=False)

        if topic == 'LOGGING' and payload_str[13:16] == 'DGR':
            print( payload_str[18:])

    elif msg.topic == 'zigbee2mqtt/bridge/devices':
        zig_groups = {}
        zig_devices = []

        payload_dict = json.loads(msg.payload)
        for zdevice in payload_dict:
            friendly_name = zdevice['friendly_name']
            if len(friendly_name) > 3:
                split_zdevice = friendly_name.split('_')
                if split_zdevice[-1] == 'DGR': # then include in device groups
                    zgroup = split_zdevice[-2]

                    if zgroup in zig_groups:
                        zig_groups[zgroup].append(friendly_name)
                    else:
                        zig_groups[zgroup] = [friendly_name]

                    if friendly_name not in zig_devices:
                        zig_devices.append(friendly_name)
                        client.subscribe('zigbee2mqtt/%s' % friendly_name)

                    print(zgroup, friendly_name)
    
    elif msg.topic.startswith('zigbee2mqtt'):
        split_topic = msg.topic.split('/')
        friendly_name = split_topic[1]
        if friendly_name in zig_devices:
            print(friendly_name, payload_str)

client = mqtt.Client(MQTT_CLIENT)
client.username_pw_set(MQTT_USER , MQTT_PASSWORD)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, port=MQTT_PORT)

client.loop_forever()