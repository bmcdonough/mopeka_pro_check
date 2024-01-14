#!/usr/bin/env python3
import re
import sys

# lines that indicate start of important info
regexp101 = re.compile(r'MopekaSensor')
regexp102 = re.compile(r'MAC')
regexp103 = re.compile(r'MopekaAdvertisement')

# patterns to match
ms_mac = re.compile(r'(?:[0-9a-fA-F]:?){12}')
ms_rssi = re.compile(r'(\-\d{1,2})dBm')

mopeka_sensors = []
mopeka_sensor = {'id': None, 'mac': None, 'rssi': None, 'batteryV': None, 'batteryPCT': None, 'tempC': None, 'tempF': None, 'stars': None, 'fluidMM': None}
id = 0

while True:
    try:
        for line in sys.stdin:
            print("\n")
            print("#DEBUG line: {}".format(line))
            match101 = regexp101.findall(line)
            if len(match101)>0:     # next sensor
                mopeka_sensors.append(mopeka_sensor)
                mopeka_sensors[id]['id'] = id
            match102 = regexp102.findall(line)
            if len(match102)>0:     # found MAC address
                ms_mac_match = ms_mac.findall(line)
                mopeka_sensors[id]['mac'] = ms_mac_match
            match103 = regexp103.findall(line)
            if len(match103)>0:     # found sensor values
                ms_rssi_match = ''.join(ms_rssi.findall(line))
                print("#DEBUG: ms_rssi_match type:{} value:{}".format(type(int(ms_rssi_match)),int(ms_rssi_match)))
                mopeka_sensors[id]['rssi'] = int(ms_rssi_match)
            print("#DEBUG: id {}".format(id))
            print("#DEBUG: mopeka_sensors {}".format(mopeka_sensors))
#            if mopeka_sensors[id]['rssi']:
#                print("#DEBUG: mopeka_sensors {}".format(mopeka_sensors))
#                id += 1
    except EOFError:
        break
