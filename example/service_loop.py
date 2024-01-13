from mopeka_pro_check.service import MopekaService, MopekaSensor, GetServiceInstance
from time import sleep

service = GetServiceInstance()
service.SetHostControllerIndex(0)
print("Do Discovery")
service.DoSensorDiscovery()

while True:
    print("Service Loop")
    service.Start()
    sleep(10)
    service.Stop()
    for s in service.SensorDiscoveredList.values():
        s.Dump()
