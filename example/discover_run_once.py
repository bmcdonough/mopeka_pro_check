#!/usr/bin/env python3
import sys
import asyncio # Import asyncio
from mopeka_pro_check.service import GetServiceInstance # MopekaService and MopekaSensor not directly used here
from time import sleep

async def main_run_once(): # Make the main logic asynchronous
    service = GetServiceInstance()
    service.SetHostControllerIndex(0)
    print("Do Discovery")
    await service.DoSensorDiscovery() # This calls asyncio.create_task(self.Stop()) if already running

    await service.Start() # service.Start() is async
    await asyncio.sleep(15) # Use asyncio.sleep
    await service.Stop() # service.Stop() is async
    for s in service.SensorDiscoveredList.values():
        s.Dump()
    sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main_run_once()) # Run the async main_loop
    sys.exit()