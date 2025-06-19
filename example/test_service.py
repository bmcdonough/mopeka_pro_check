#!/usr/bin/env python3

import asyncio
import logging
import time # Keep for synchronous sleep if needed, but prefer asyncio.sleep

from mopeka_pro_check.service import GetServiceInstance, ServiceScanningMode
from mopeka_pro_check.sensor import MopekaSensor

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

# Replace with your sensor's MAC address if testing FILTERED_MODE
EXAMPLE_MAC_ADDRESS = "XX:XX:XX:XX:XX:XX" # e.g., "E7:9D:05:C4:3C:76"

async def run_filtered_mode(mac_address_to_monitor: str):
    _LOGGER.info(f"Starting filtered mode for MAC: {mac_address_to_monitor}")
    service = GetServiceInstance()
    await service.Stop() # Ensure any previous scan is stopped
    service.SensorMonitoredList.clear() # Clear previous monitored sensors

    sensor = MopekaSensor(mac_address_to_monitor)
    await service.AddSensorToMonitor(sensor)
    service.SetScanningMode(ServiceScanningMode.FILTERED_MODE) # Explicitly set mode

    await service.Start()
    _LOGGER.info("Scanning started in FILTERED_MODE. Press Ctrl+C to stop.")
    try:
        for _ in range(30): # Run for 30 seconds for this example
            reading = sensor.GetReading()
            if reading:
                _LOGGER.info(f"Sensor {sensor._mac} reading: {reading}")
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        _LOGGER.info("Keyboard interrupt received.")
    finally:
        _LOGGER.info("Stopping filtered mode scan...")
        await service.Stop()
        _LOGGER.info(f"Stats: {service.ServiceStats}")

async def run_discovery_mode():
    _LOGGER.info("Starting discovery mode...")
    service = GetServiceInstance()
    await service.Stop() # Ensure any previous scan is stopped
    service.DoSensorDiscovery() # This sets mode to DISCOVERY_MODE and clears lists

    await service.Start()
    _LOGGER.info("Scanning started in DISCOVERY_MODE. Press Ctrl+C to stop.")
    _LOGGER.info("Press the sync button on your Mopeka sensors.")
    try:
        await asyncio.sleep(30) # Discover for 30 seconds
    except KeyboardInterrupt:
        _LOGGER.info("Keyboard interrupt received.")
    finally:
        _LOGGER.info("Stopping discovery mode scan...")
        await service.Stop()
        _LOGGER.info(f"Finished Discovery. Found {len(service.SensorDiscoveredList)} new sensors.")
        _LOGGER.info(f"Stats: {service.ServiceStats}")
        for s in service.SensorDiscoveredList.values():
            s.Dump()

async def main():
    # Choose which mode to run
    # await run_discovery_mode()
    if EXAMPLE_MAC_ADDRESS == "XX:XX:XX:XX:XX:XX":
        _LOGGER.warning("EXAMPLE_MAC_ADDRESS is not set. Running discovery mode instead.")
        await run_discovery_mode()
    else:
        await run_filtered_mode(EXAMPLE_MAC_ADDRESS)

if __name__ == "__main__":
    asyncio.run(main())
