"""Module that represents a Mopeka Pro Check sensor.

Sensor object stores meta info and the last reading.
It also could support an idea of holding more than one
reading.

Copyright (c) 2021 Sean Brogan

SPDX-License-Identifier: MIT

"""
from typing import Optional

from .advertisement import MopekaAdvertisement

class MopekaSensor(object):
  """ Sensor Object """

  _mac: str
  # _bdaddress is no longer needed as simplepyble uses string MACs
  _last_packet: Optional[MopekaAdvertisement]

  def __init__(self, mac_address:str ):
    self._mac = mac_address
    # self._bdaddress = BDAddress(mac_address) # Removed bleson specific BDAddress
    self._last_packet: Optional[MopekaAdvertisement] = None

  def AddReading(self, reading_data: MopekaAdvertisement):
    self._last_packet = reading_data

  def GetReading(self) -> Optional[MopekaAdvertisement]:
    """ return the most recent packet and clear it """
    t = self._last_packet
    self._last_packet = None
    return t

  def __str__(self) -> str:
    return f"{{MopekaSensor - MAC ADDRESS: {self._mac} {self._last_packet}}}"

  def Dump(self):
    print(f"MopekaSensor:")
    print(f"  - MAC: {self._mac}")
    a = self._last_packet
    if a:
      print("  - Advertisement: ")
      a.Dump()
    else:
      print(f"  - Advertisement: None")
