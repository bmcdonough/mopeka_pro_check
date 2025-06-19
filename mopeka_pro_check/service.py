"""Singleton service supporting Mopeka Propane Tank Level Sensors

Many ideas were borrowed from the MIT licensed project here:
https://github.com/Home-Is-Where-You-Hang-Your-Hack/sensor.goveetemp_bt_hci
Code was written referencing that project but it is so significantly different that I am not
including that projects original copyright.


Copyright (c) 2021 Sean Brogan

SPDX-License-Identifier: MIT

"""
import asyncio
import logging
from enum import Enum
from typing import Optional, Dict, List # List might be needed for simplepyble.Adapter.get_adapters()
import simplepyble
from .advertisement import MopekaAdvertisement, NoGapDataException, MOPEKA_MANUFACTURE_ID
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
  """ Class uses ble stack to listen for advertisements and update data
  This service uses bleson which as of 0.1.8 only actually works on Linux"""

  SensorMonitoredList: Dict[str, MopekaSensor] # MAC address (str) is the key
  """ Sensor data received while in Filtered mode per sensor """

  SensorDiscoveredList: Dict[str, MopekaSensor] # MAC address (str) is the key
  """ New Sensors discovered while scanning in Discovery mode """

  ServiceStats: ReadStats
  """ Stats for the latest scanning session"""

  _hci_index: int
  _adapter: Optional[simplepyble.Adapter]
  _scanning_task: Optional[asyncio.Task]
  _should_start: bool

  def __init__(self):
    """ Create a MopekaService instance

    Service is not started upon creation

    """
    self._hci_index = 0
    self._scanning_task = None
    self._should_start = False
    self._adapter = None
    self._scanning_mode = ServiceScanningMode.FILTERED_MODE

    self.SensorMonitoredList = dict()
    self.SensorDiscoveredList = dict()
    self.ServiceStats = ReadStats()

  def SetHostControllerIndex(self, index:int) -> bool:
    """ Set the host controller index to bind to.
    This can only be called prior to starting any scanning
    """

    if self._adapter is not None:
      #already started
      return False

    self._hci_index = index
    return True

  def DoSensorDiscovery(self):
    """ Setup the service to scan for all Mopeka sensors
    with the button pressed.  This is how sensors should be
    discovered.

    Note: this will stop any current scan process.
    Note: this will not start scanning
    Note: this will clear any previously discovered sensors
    Note: this will clear all statistics
    """ # Make this async if Stop is async
    asyncio.create_task(self.Stop()) # Stop if running, fire and forget
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
      await self.Stop()  # stop processing so that we can safely update the shared list

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
        self.SensorMonitoredList.pop(sensor._bdaddress, None) # Pop by key

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

    if self._adapter is None:
        adapters: List[simplepyble.Adapter] = simplepyble.Adapter.get_adapters()
        if not adapters:
            _LOGGER.error("No BLE adapters found.")
            raise Exception("No BLE adapters found.")
        if self._hci_index >= len(adapters):
            _LOGGER.error(f"Adapter index {self._hci_index} out of range. Available: {len(adapters)}")
            raise Exception(f"Adapter index {self._hci_index} out of range.")
        self._adapter = adapters[self._hci_index]
        _LOGGER.info(f"Using adapter: {self._adapter.identifier()} [{self._adapter.address()}]")

    if self._adapter is None: # Should not happen if logic above is correct
        _LOGGER.error("Adapter not initialized.")
        return

    _LOGGER.info(f"Starting Mopeka service scan in {self._scanning_mode.name} mode...")
    self._adapter.set_callback_on_scan_start(lambda: _LOGGER.info("Scan started."))
    self._adapter.set_callback_on_scan_stop(lambda: _LOGGER.info("Scan stopped."))
    self._adapter.set_callback_on_scan_found(self._handle_advertisement_callback)

    self._scanning_task = asyncio.create_task(self._scan_loop())

  async def _scan_loop(self):
      if not self._adapter:
          _LOGGER.error("Adapter not available for scanning loop.")
          return
      try:
          # simplepyble's scan_start is non-blocking and uses callbacks.
          # The scan_for method is blocking for its duration.
          # We'll use scan_start and let the callback handle ads.
          await self._adapter.scan_start()
          while self._should_start:
              if not self._adapter.scan_is_active():
                  _LOGGER.warning("Scan became inactive unexpectedly. Attempting to restart.")
                  await self._adapter.scan_start()
              await asyncio.sleep(1) # Keep loop alive, check _should_start
      except simplepyble.BleakError as e: # simplepyble might raise BleakError
          _LOGGER.error(f"Simplepyble BLE error during scan: {e}")
      except Exception as e:
          _LOGGER.error(f"Error during scan loop: {e}")
      finally:
          if self._adapter and self._adapter.scan_is_active():
              await self._adapter.scan_stop()
          _LOGGER.info("Mopeka service scan loop ended.")
          self._scanning_task = None # Clear task when loop finishes or is cancelled

  async def Stop(self) -> None:
    """ stop scanning"""
    self._should_start = False
    if self._scanning_task and not self._scanning_task.done():
        _LOGGER.info("Stopping scan task...")
        self._scanning_task.cancel()
        try:
            await self._scanning_task # Wait for task to acknowledge cancellation
        except asyncio.CancelledError:
            _LOGGER.info("Scan task successfully cancelled.")
        except Exception as e: # Catch other potential errors during task cancellation
            _LOGGER.error(f"Error during scan task cancellation: {e}")
    # Ensure scan_stop is called even if task was already done or None
    if self._adapter and self._adapter.scan_is_active():
        await self._adapter.scan_stop()
    self._scanning_task = None # Ensure task is cleared

  def _handle_advertisement_callback(self, peripheral: simplepyble.Peripheral) -> None:
    """ Callback function for simplepyble advertisements """
    mac = peripheral.address()
    rssi = peripheral.rssi()
    # simplepyble's Peripheral object might not have a direct 'name' attribute.
    # Name is usually part of advertisement data, which simplepyble provides separately
    # or sometimes through peripheral.identifier() if it's the local name.
    # We'll try peripheral.identifier() and then look into advertisement_data if available.
    # For simplepyble, the advertisement data is often accessed via peripheral.advertisement_data()
    # or passed to the callback. Let's assume peripheral.identifier() gives a usable name for now.
    name = peripheral.identifier()
    
    # Manufacturer data is a dictionary {company_id: data_bytes}
    mopeka_mfg_payload = peripheral.manufacturer_data().get(MOPEKA_MANUFACTURE_ID)

    if self._scanning_mode == ServiceScanningMode.FILTERED_MODE:
      # Filtered Mode is scanning and only processing known sensors
      sensor = self.SensorMonitoredList.get(mac)
      if sensor is not None:
        if mopeka_mfg_payload:
            try:
                # Construct the full manufacturer data expected by MopekaAdvertisement
                # [GAP_AD_TYPE (0xFF), MFG_ID_LSB (0x59), MFG_ID_MSB (0x00), Mopeka_Payload(10 bytes)]
                mfg_data_full = bytes([MopekaAdvertisement.GAP_MFG_DATA,
                                       MOPEKA_MANUFACTURE_ID & 0xFF, 
                                       (MOPEKA_MANUFACTURE_ID >> 8) & 0xFF]) + mopeka_mfg_payload
                
                ma = MopekaAdvertisement(mac=mac, rssi=rssi, name=name, mfg_data=mfg_data_full)
                sensor.AddReading(ma)
                self.ServiceStats._processed_ad_count += 1
            except Exception as e:
                _LOGGER.error(f"Failed to process advertisement from defined sensor {mac}. Exception: {e}")
                self.ServiceStats._error_ad_count += 1 # Count as error
        else:
             self.ServiceStats._ignored_ad_count += 1 # No Mopeka data
      else:
        self.ServiceStats._ignored_ad_count += 1

    elif self._scanning_mode == ServiceScanningMode.DISCOVERY_MODE:
      # Discovery mode is looking for all Mopeka Sensors and reporting
      # them if their sync button is pressed
      if mopeka_mfg_payload:
        sensor = self.SensorDiscoveredList.get(mac)
        try:
            mfg_data_full = bytes([MopekaAdvertisement.GAP_MFG_DATA,
                                   MOPEKA_MANUFACTURE_ID & 0xFF, 
                                   (MOPEKA_MANUFACTURE_ID >> 8) & 0xFF]) + mopeka_mfg_payload
            ma = MopekaAdvertisement(mac=mac, rssi=rssi, name=name, mfg_data=mfg_data_full)
            _LOGGER.info(f"Discovery Mode - MopekaAdvertisement: {ma.mac} @ {ma.rssi}dBm")
            self.ServiceStats._processed_ad_count += 1

#          if(ma.SyncButtonPressed):
            # Only sensors with button pressed should be discovered
            # Recommendation by Mopeka
          # The original code added if NOT sync button pressed (promiscuous).
          # To discover only on sync button press, use: if ma.SyncButtonPressed:
          # For now, retaining promiscuous-like behavior for all Mopeka sensors found:
            if sensor is None: # Add if new
              # promiscuous mode
              sensor = MopekaSensor(mac)
              sensor.AddReading(ma)
              self.SensorDiscoveredList[mac] = sensor
              _LOGGER.info(f"Discovered new Mopeka sensor: {mac}")
            else: # Update existing discovered sensor
              sensor.AddReading(ma)
            
        except Exception as e:
            _LOGGER.error(f"Failed to process advertisement in discovery mode from {mac}. Exception: {e}")
            self.ServiceStats._error_ad_count += 1 # Count as error
      else:
          self.ServiceStats._ignored_ad_count += 1 # Not Mopeka or no mfg data

######################################################################################
## Global Functions
######################################################################################
def GetServiceInstance() -> MopekaService:
  """ Function to support getting the Singleton instance of the Mopeka Service"""
  global GlobalService
  if GlobalService is None:
    GlobalService = MopekaService()
  return GlobalService
