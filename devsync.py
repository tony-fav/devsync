import os
import json
import paho.mqtt.client as mqtt

from secrets import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, MQTT_CLIENT


# todo: define a class/object that is the device group, stores name, devices in it, state, etc...
# todo: use more of the zigbee2mqtt definition to get if it's a light or plug or w/e color_temp range, brightness range, ct range, etc...

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
tas_last_message = {}

zig_groups = {}
zig_devices = []

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    global tas_groups
    global tas_devices
    global tas_last_message
    global zig_groups
    global zig_devices

    try:
        payload_str = str(msg.payload.decode("utf-8"))
    except:
        payload_str = ''
    
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

                if device not in tas_last_message:
                    tas_last_message[device] = ''

        if topic == 'LOGGING' and payload_str[13:16] == 'DGR':
            dg_log = payload_str[18:].replace(' (old)', '')
            pre_colon, post_colon = (x.strip() for x in dg_log.split(':'))
            dg_name = pre_colon.split(' ')[1]
            split_post_color = (x.strip() for x in post_colon.split(', '))
            dg_args = {x[0]: x[1] for x in [y.split('=') for y in split_post_color]}
            dg_flags = int(dg_args['flags'])
            if dg_flags == 0:
                log_msg = '%s, %s' % (dg_name, dg_args)
                for k, v in dg_args.items():
                    v = v.replace('*','')
                    if k == '128':
                        bm = bin(int(v))[2:]
                        bm = '0'*(32-len(bm)) + bm
                        relay_count = int(bm[0:8],2)
                        relay_bitmask = bm[8:][::-1]
                        for r in range(relay_count):
                            log_msg += ': Relay %d = %s' % (r+1, relay_bitmask[r])

                print(log_msg)
            if dg_flags & 1:
                print(dg_name, 'DGR_FLAG_RESET')
            if dg_flags & 2:
                print(dg_name, 'DGR_FLAG_STATUS_REQUEST')
            if dg_flags & 4:
                print(dg_name, 'DGR_FLAG_FULL_STATUS')
            if dg_flags & 8:
                pass
                # print(dg_name, 'DGR_FLAG_ACK')
            if dg_flags & 16:
                print(dg_name, 'DGR_FLAG_MORE_TO_COME')
            if dg_flags & 32:
                print(dg_name, 'DGR_FLAG_DIRECT')
            if dg_flags & 64:
                pass
                # print(dg_name, 'DGR_FLAG_ANNOUNCEMENT')
            if dg_flags & 128:
                print(dg_name, 'DGR_FLAG_LOCAL')

    elif msg.topic == 'zigbee2mqtt/bridge/devices':
        zig_groups = {}
        zig_devices = []

        payload_dict = json.loads(msg.payload)
        for zdevice in payload_dict:
            friendly_name = zdevice['friendly_name']
            if len(friendly_name) > 3:
                split_zdevice = friendly_name.split('_')
                if split_zdevice[-1] == 'DGR': # then include in device groups
                    print(zdevice)
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