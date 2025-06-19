#!/usr/bin/env python3
import sys
import asyncio # Import asyncio
from mopeka_pro_check.service import GetServiceInstance # MopekaService and MopekaSensor not directly used here
from time import sleep

async def main_loop(): # Make the main logic asynchronous
    service = GetServiceInstance()
    service.SetHostControllerIndex(0)
    print("Do Discovery")
    # DoSensorDiscovery is now async and needs to be awaited
    await service.DoSensorDiscovery()

    try:
        while True:
            print("Service Loop - Starting scan...")
            await service.Start() # service.Start() is async
            await asyncio.sleep(60) # Use asyncio.sleep
            print("Service Loop - Stopping scan...")
            await service.Stop() # service.Stop() is async
            for s in service.SensorDiscoveredList.values():
                s.Dump()
            sys.stdout.flush()
    except KeyboardInterrupt:
        print("Loop interrupted. Stopping service.")
        await service.Stop()

if __name__ == "__main__":
    asyncio.run(main_loop()) # Run the async main_loop