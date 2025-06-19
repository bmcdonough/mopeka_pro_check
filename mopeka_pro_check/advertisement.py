"""Mopeka Propane Tank Level Sensor BLE Advertisement parser

Copyright (c) 2021 Sean Brogan

SPDX-License-Identifier: MIT

"""
from enum import Enum
import logging
from typing import Optional
# import simplepyble # Not directly used here, but simplepyble is the source of data

# converting sensor value to height - contact Mopeka for other fluids/gases
MOPEKA_TANK_LEVEL_COEFFICIENTS_PROPANE = (0.573045, -0.002822, -0.00000535)

MOPEKA_MANUFACTURE_ID = 0x0059
# Standard Bluetooth GAP AdType for Manufacturer Specific Data
GAP_MFG_DATA = 0xFF

_LOGGER = logging.getLogger(__name__)

class NoGapDataException(Exception):
    """ Special subclass to gracefully handle zero length GAP
    caller should catch these exception types specifically
    """
    pass


class HardwareId(Enum):
    """ definition of the known Mopeka hardware ids."""
    STD_BOTTOM_UP_PROPANE = 0x3
    TOP_DOWN_AIR_SPACE = 0x4
    BOTTOM_UP_WATER = 0x5
    PRO_CHECK_UNIVERSAL = 0xC     # decimal 12, p/n M1017020A 


class MopekaAdvertisement:
    """ Represents a parsed Mopeka sensor BLE advertisement.

    This class is designed to be initialized with parsed data obtained
    from a BLE scanning library like simpleble, not raw HCI packets.
    """

    rssi: int
    name: Optional[str]
    mac: str # simpleble uses string for MAC address

    # Private Members
    _raw_mfg_data: bytes
    _raw_battery: int
    _raw_temp: int
    _raw_tank_level: int
    _raw_x_accel: int
    _raw_y_accel: int

    def __init__(self, mac: str, rssi: int, name: Optional[str], mfg_data: bytes):
        """ Initialize from parsed BLE advertising data.

        Args:
            mac: The sensor's MAC address (string).
            rssi: The received signal strength indicator (int).
            name: The sensor's advertised name (string or None).
            mfg_data: The manufacturer data bytes, expected to be pre-formatted by
                      the caller (MopekaService) to include:
                      [GAP_AD_TYPE (0xFF), MFG_ID_LSB (0x59), MFG_ID_MSB (0x00), 10-byte Mopeka payload]
        """
        self.mac = mac
        self.rssi = rssi
        self.name = name
        self._raw_mfg_data = mfg_data

        # Parse the Mopeka specific manufacturer data
        self._parse_mopeka_mfg_data(mfg_data)

    def _parse_mopeka_mfg_data(self, data: bytes) -> None:
        """ Parse the Mopeka specific manufacturer data bytes.

        data should be buffer starting with type and have length matching
        the report length.
        """

        if data[0] == GAP_MFG_DATA:
            self._process_gap_mfg_data(data)
        else:
            _LOGGER.debug(
                "Unexpected data type in manufacturer data: 0x%X on sensor %s",
                data[0], self.mac
            )

    def _process_gap_mfg_data(self, data: bytes) -> None:
        """ process GAP data of type GAP_MFG_DATA

        data should be buffer in format defined by Mopeka
        """
        # data is [GAP_TYPE (0xFF), CompanyID_LSB, CompanyID_MSB, Mopeka_Payload(10 bytes)]
        # Total length should be 1 (type) + 2 (mfg_id) + 10 (payload) = 13 bytes
        expected_total_len = 13
        MfgDataLength = len(data) # Define MfgDataLength
        if MfgDataLength != expected_total_len:
            raise Exception(f"Unsupported Data Length (0x{MfgDataLength:X})")

        self.ManufacturerId = data[1] + (data[2] << 8)
        if self.ManufacturerId != MOPEKA_MANUFACTURE_ID:
            raise Exception(
                f"Advertising Data has Unsupported Manufacturer ID 0x{self.ManufacturerId}"
            )

        self.HardwareId = HardwareId(data[3])
        if not isinstance(self.HardwareId, HardwareId):
            _LOGGER.error("Mopeka Sensor %s has Unsupported Hardware ID %s", self.mac, hex(data[3]))

        self._raw_battery = data[4] & 0x7F

        self.SyncButtonPressed = bool(data[5] & 0x80 > 0)
        """ True if Sync Button is currently pressed """

        self._raw_temp = data[5] & 0x7F
        self._raw_tank_level = ((int(data[7]) << 8) + data[6]) & 0x3FFF

        self.ReadingQualityStars = data[7] >> 6
        """ Confidence or Quality of the reading on a scale of 0-3.  Higher is more confident """

        self._raw_x_accel = data[11]
        self._raw_y_accel = data[12]

    @property
    def BatteryVoltage(self) -> float:
        """Battery reading in volts"""
        return self._raw_battery / 32.0

    @property
    def BatteryPercent(self) -> float:
        """Battery Percentage based on 3 volt CR2032 battery"""
        percent = ((self.BatteryVoltage - 2.2) / 0.65) * 100
        if percent > 100.0:
            return 100.0
        if percent < 0.0:
            return 0.0
        return round(percent, 1)

    @property
    def TemperatureInCelsius(self) -> int:
        """Temperature in Celsius

        Note: This temperature has not been characterized against ambient temperature
        """
        return self._raw_temp - 40

    @property
    def TemperatureInFahrenheit(self) -> float:
        """Temperature in Fahrenheit

        Note: This temperature has not been characterized against ambient temperature
        """
        return ((self.TemperatureInCelsius * 9) / 5) + 32

    @property
    def TankLevelInMM(self) -> int:
        """ The tank level/depth in mm for propane gas"""
        return int(
            self._raw_tank_level
            * (
                MOPEKA_TANK_LEVEL_COEFFICIENTS_PROPANE[0]
                + (MOPEKA_TANK_LEVEL_COEFFICIENTS_PROPANE[1] * self._raw_temp)
                + (
                    MOPEKA_TANK_LEVEL_COEFFICIENTS_PROPANE[2]
                    * self._raw_temp
                    * self._raw_temp
                )
            )
        )

    @property
    def TankLevelInInches(self) -> float:
        """ The tank level/depth in inches"""
        return round(self.TankLevelInMM / 25.4, 2)

    def __str__(self) -> str:
        return ("MopekaAdvertisement -  " +
                f"MAC: {self.mac}  " +
                f"RSSI: {self.rssi}dBm  " +
                f"Battery: {self.BatteryVoltage} volts {self.BatteryPercent}%  " +
                f"Button Pressed: {self.SyncButtonPressed}  " +
                f"Temperature {self.TemperatureInCelsius}C {self.TemperatureInFahrenheit}F  " +
                f"Confidence Stars {self.ReadingQualityStars}  " +
                f"Fluid Height {self.TankLevelInMM} mm")

    def Dump(self):
        """ Helper routine that prints ad data plus all mfg data"""
        print(self)
        print("Raw MfgData: ", end="")
        for a in self._raw_mfg_data:
            print("0x%02X" % a, end="  ")
        print("\n")
