#!/usr/bin/env python3
import sys
from mopeka_pro_check.service import MopekaService, MopekaSensor, GetServiceInstance
from time import sleep

service = GetServiceInstance()
service.SetHostControllerIndex(0)
print("Do Discovery")
service.DoSensorDiscovery()

while True:
    print("Service Loop")
    service.Start()
    sleep(60)
    service.Stop()
    for s in service.SensorDiscoveredList.values():
        s.Dump()
    sys.stdout.flush()