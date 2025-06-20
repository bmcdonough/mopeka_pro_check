"""Singleton service supporting Mopeka Propane Tank Level Sensors - Bleak Version

Copyright (c) 2021 Sean Brogan

SPDX-License-Identifier: MIT

"""
import asyncio
import logging
from enum import Enum
from typing import Optional, Dict, List, Tuple
from bleak import BleakScanner, BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from .advertisement import MopekaAdvertisement, NoGapDataException, MOPEKA_MANUFACTURE_ID, GAP_MFG_DATA
from .sensor import MopekaSensor

_LOGGER = logging.getLogger(__name__)
GlobalService = None

class ReadStats(object):
  """ Simple object to store different statistics related
  to service operations"""

  _ignored_ad_count: int
  _processed_ad_count: int
  _error_ad_count: int
  _zero_length_ad_count: int

  def __init__(self):
    self._ignored_ad_count = 0
    self._processed_ad_count = 0
    self._error_ad_count = 0
    self._zero_length_ad_count = 0

  def __str__(self):
    return f"ReadStats ( Ignored Ad Count: {self._ignored_ad_count}, Processed Ad Count: {self._processed_ad_count}, Error Ad Count: {self._error_ad_count}), Zero Data Ad Count: {self._zero_length_ad_count})"

class ServiceScanningMode(Enum):
  """ Enum to define different supported scanning modes for the service"""
  FILTERED_MODE = 0
  """ Scan looking for known sensors and collect their advertisements"""

  DISCOVERY_MODE = 1
  """ Scan looking for sensors with their sync button pressed"""


class MopekaService(object):
  """ Class uses bleak to listen for advertisements and update data """

  SensorMonitoredList: Dict[str, MopekaSensor] # MAC address (str) is the key
  """ Sensor data received while in Filtered mode per sensor """

  SensorDiscoveredList: Dict[str, MopekaSensor] # MAC address (str) is the key
  """ New Sensors discovered while scanning in Discovery mode """

  ServiceStats: ReadStats
  """ Stats for the latest scanning session"""

  _hci_index: int
  _scanner: Optional[BleakScanner]
  _scanning_task: Optional[asyncio.Task]
  _should_start: bool

  def __init__(self):
    """ Create a MopekaService instance

    Service is not started upon creation

    """
    self._hci_index = 0
    self._scanning_task = None
    self._should_start = False
    self._scanner = None
    self._scanning_mode = ServiceScanningMode.FILTERED_MODE

    self.SensorMonitoredList = dict()
    self.SensorDiscoveredList = dict()
    self.ServiceStats = ReadStats()

  def SetHostControllerIndex(self, index:int) -> bool:
    """ Set the host controller index to bind to.
    This can only be called prior to starting any scanning
    """

    if self._scanner is not None:
      #already started
      return False

    self._hci_index = index
    return True

  async def DoSensorDiscovery(self) -> None:
    """ Setup the service to scan for all Mopeka sensors
    with the button pressed.  This is how sensors should be
    discovered.

    Note: this will stop any current scan process.
    Note: this will not start scanning
    Note: this will clear any previously discovered sensors
    Note: this will clear all statistics
    """
    if self._scanning_task is not None and not self._scanning_task.done():
        await self.Stop()
    self.SensorDiscoveredList.clear()
    self._scanning_mode = ServiceScanningMode.DISCOVERY_MODE
    self.ServiceStats = ReadStats()

  async def AddSensorToMonitor(self, sensor: MopekaSensor) -> None:
    """ Add a sensor that should be monitored when scanning in filtered mode.
    If the sensor mac address is already listed the sensor will be replaced with
    new sensor.

    Note: Scanning will be stopped while the sensor is added
    """
    if self._scanning_mode == ServiceScanningMode.FILTERED_MODE:
      await self.Stop()

    self.SensorMonitoredList[sensor._bdaddress] = sensor

    # restart scanning if it was previously scanning in filtered mode
    if self._scanning_mode == ServiceScanningMode.FILTERED_MODE and self._should_start:
      await self._start_scanning_task()
    return

  async def RemoveSensorToMonitor(self, sensor: MopekaSensor) -> None:
    """ Remove a sensor from the list to be monitored.  If the sensor isn't
    found in the list just return.

    Note: Scanning will be stopped while the sensor is removed

    """
    if sensor._bdaddress in self.SensorMonitoredList:
        if self._scanning_mode == ServiceScanningMode.FILTERED_MODE:
            await self.Stop()
        self.SensorMonitoredList.pop(sensor._bdaddress, None)

        if self._scanning_mode == ServiceScanningMode.FILTERED_MODE and self._should_start:
            await self._start_scanning_task()

  async def Start(self) -> None:
    """ Start scanning """
    self._should_start = True
    await self._start_scanning_task()

  async def _start_scanning_task(self) -> None:
    """ Internal function to start the scanning asyncio task """
    if self._scanning_task and not self._scanning_task.done():
        _LOGGER.info("Scanning is already in progress.")
        return

    # don't start unless there is a sensor list to filter for
    if self._scanning_mode == ServiceScanningMode.FILTERED_MODE and len(self.SensorMonitoredList) == 0:
        _LOGGER.info("Filtered mode: No sensors to monitor. Scan not started.")
        return

    # Create scanner if needed
    if self._scanner is None:
        # For bleak, we can specify adapter via adapter parameter, but it takes device name like "hci0"
        adapter_name = f"hci{self._hci_index}" if self._hci_index >= 0 else None
        try:
            self._scanner = BleakScanner(
                detection_callback=self._handle_advertisement_callback,
                adapter=adapter_name
            )
            _LOGGER.info(f"Using BLE adapter: {adapter_name or 'default'}")
        except Exception as e:
            _LOGGER.error(f"Failed to create BLE scanner: {e}")
            raise Exception(f"Failed to create BLE scanner: {e}")

    _LOGGER.info(f"Starting Mopeka service scan in {self._scanning_mode.name} mode...")
    self._scanning_task = asyncio.create_task(self._scan_loop())

  async def _scan_loop(self):
      if not self._scanner:
          _LOGGER.error("Scanner not available for scanning loop.")
          return
      try:
          _LOGGER.info("Starting BLE scan...")
          await self._scanner.start()
          
          while self._should_start:
              await asyncio.sleep(1)  # Keep loop alive, check _should_start
              
      except Exception as e:
          _LOGGER.error(f"Error during scan loop: {e}")
      finally:
          if self._scanner:
              await self._scanner.stop()
          _LOGGER.info("Mopeka service scan loop ended.")
          self._scanning_task = None

  async def Stop(self) -> None:
    """ stop scanning"""
    self._should_start = False
    if self._scanning_task and not self._scanning_task.done():
        _LOGGER.info("Stopping scan task...")
        try:
            self._scanning_task.cancel()
            await self._scanning_task
        except asyncio.CancelledError:
            _LOGGER.info("Scan task cancelled successfully.")
        except Exception as e:
            _LOGGER.error(f"Error during scan task cancellation: {e}")
    
    # Ensure scanner is stopped
    if self._scanner:
        try:
            await self._scanner.stop()
        except Exception as e:
            _LOGGER.debug(f"Error stopping scanner: {e}")
    self._scanning_task = None

  def _handle_advertisement_callback(self, device: BLEDevice, advertisement_data: AdvertisementData) -> None:
    """ Callback function for bleak advertisements """
    mac = device.address
    rssi = advertisement_data.rssi if advertisement_data.rssi is not None else -999
    name = advertisement_data.local_name or device.name
    
    # Get Mopeka manufacturer data
    mopeka_mfg_payload = advertisement_data.manufacturer_data.get(MOPEKA_MANUFACTURE_ID)

    if self._scanning_mode == ServiceScanningMode.FILTERED_MODE:
      # Filtered Mode is scanning and only processing known sensors
      sensor = self.SensorMonitoredList.get(mac)
      if sensor is not None:
        if mopeka_mfg_payload:
            try:
                # Construct the full manufacturer data expected by MopekaAdvertisement
                # [GAP_AD_TYPE (0xFF), MFG_ID_LSB (0x59), MFG_ID_MSB (0x00), Mopeka_Payload(10 bytes)]
                mfg_data_full = bytes([GAP_MFG_DATA,
                                       MOPEKA_MANUFACTURE_ID & 0xFF, 
                                       (MOPEKA_MANUFACTURE_ID >> 8) & 0xFF]) + mopeka_mfg_payload
                
                ma = MopekaAdvertisement(mac=mac, rssi=rssi, name=name, mfg_data=mfg_data_full)
                sensor.AddReading(ma)
                self.ServiceStats._processed_ad_count += 1
            except Exception as e:
                _LOGGER.error(f"Failed to process advertisement from defined sensor {mac}. Exception: {e}")
                self.ServiceStats._error_ad_count += 1
        else:
             self.ServiceStats._ignored_ad_count += 1
      else:
        self.ServiceStats._ignored_ad_count += 1

    elif self._scanning_mode == ServiceScanningMode.DISCOVERY_MODE:
      # Discovery mode is looking for all Mopeka Sensors and reporting
      # them if their sync button is pressed
      if mopeka_mfg_payload:
        sensor = self.SensorDiscoveredList.get(mac)
        try:
            # Construct the full manufacturer data expected by MopekaAdvertisement
            mfg_data_full = bytes([GAP_MFG_DATA,
                                   MOPEKA_MANUFACTURE_ID & 0xFF, 
                                   (MOPEKA_MANUFACTURE_ID >> 8) & 0xFF]) + mopeka_mfg_payload
            
            ma = MopekaAdvertisement(mac=mac, rssi=rssi, name=name, mfg_data=mfg_data_full)
            
            if sensor is None:
              sensor = MopekaSensor(mac)
              self.SensorDiscoveredList[mac] = sensor
            
            sensor.AddReading(ma)
            self.ServiceStats._processed_ad_count += 1
            
        except NoGapDataException:
            self.ServiceStats._zero_length_ad_count += 1
        except Exception as e:
            _LOGGER.error(f"Failed to process advertisement from discovered sensor {mac}. Exception: {e}")
            self.ServiceStats._error_ad_count += 1
      else:
        self.ServiceStats._ignored_ad_count += 1


def GetServiceInstance() -> MopekaService:
  """ Get the singleton service instance """
  global GlobalService
  if GlobalService is None:
    GlobalService = MopekaService()
  return GlobalService