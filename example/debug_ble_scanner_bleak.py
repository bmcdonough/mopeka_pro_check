#!/usr/bin/env python3
"""
Debug BLE scanner using bleak - shows all BLE advertisements to help troubleshoot Mopeka detection.
"""
import sys
import asyncio
import logging
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from mopeka_pro_check.advertisement import MOPEKA_MANUFACTURE_ID

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DebugBLEScanner:
    def __init__(self, adapter="hci0"):
        self.adapter = adapter
        self.scanner = None
        self.devices_found = {}
        self.advertisement_count = 0
        
    def advertisement_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        """Callback for each BLE advertisement received"""
        try:
            self.advertisement_count += 1
            
            # Get basic info
            mac_address = device.address
            rssi = advertisement_data.rssi if advertisement_data.rssi is not None else -999
            name = advertisement_data.local_name or device.name or "Unknown"
            
            # Store device info
            if mac_address not in self.devices_found:
                self.devices_found[mac_address] = {
                    'name': name,
                    'rssi': rssi,
                    'count': 0,
                    'manufacturer_data': {},
                    'service_data': {},
                    'services': []
                }
            
            device_info = self.devices_found[mac_address]
            device_info['count'] += 1
            device_info['rssi'] = rssi  # Update with latest RSSI
            
            # Check manufacturer data
            manufacturer_data = advertisement_data.manufacturer_data
            if manufacturer_data:
                for mfg_id, data in manufacturer_data.items():
                    device_info['manufacturer_data'][mfg_id] = data.hex()
                    
                    # Check if this is a Mopeka device
                    if mfg_id == MOPEKA_MANUFACTURE_ID:
                        print(f"\n🎯 MOPEKA DEVICE FOUND!")
                        print(f"   MAC: {mac_address}")
                        print(f"   Name: {name}")
                        print(f"   RSSI: {rssi}dBm")
                        print(f"   Manufacturer ID: 0x{mfg_id:04X}")
                        print(f"   Data: {data.hex()}")
                        print(f"   Data length: {len(data)} bytes")
                        
            # Check service data
            service_data = advertisement_data.service_data
            if service_data:
                for service_uuid, data in service_data.items():
                    device_info['service_data'][str(service_uuid)] = data.hex()
                    
            # Check services
            service_uuids = advertisement_data.service_uuids
            if service_uuids:
                device_info['services'] = [str(uuid) for uuid in service_uuids]
                    
            # Print every 10th advertisement for progress
            if self.advertisement_count % 10 == 0:
                print(f"📡 Processed {self.advertisement_count} advertisements from {len(self.devices_found)} unique devices")
                
        except Exception as e:
            logger.error(f"Error processing advertisement: {e}")
            
    async def scan(self, duration=30):
        """Start scanning for the specified duration"""
        print(f"🔍 Starting debug BLE scan for {duration} seconds...")
        print(f"   Looking for Mopeka manufacturer ID: 0x{MOPEKA_MANUFACTURE_ID:04X}")
        print(f"   Will show all BLE devices found\n")
        
        try:
            self.scanner = BleakScanner(
                detection_callback=self.advertisement_callback,
                adapter=self.adapter
            )
            
            await self.scanner.start()
            await asyncio.sleep(duration)
            
        except Exception as e:
            logger.error(f"Error during scanning: {e}")
            return False
            
        finally:
            if self.scanner:
                await self.scanner.stop()
                
        print(f"\n✅ Scan completed!")
        print(f"   Total advertisements: {self.advertisement_count}")
        print(f"   Unique devices: {len(self.devices_found)}")
        return True
        
    def print_summary(self):
        """Print summary of all found devices"""
        if not self.devices_found:
            print("\n❌ No BLE devices found at all!")
            print("   This suggests a Bluetooth adapter or permissions issue.")
            return
            
        print(f"\n📋 Summary of {len(self.devices_found)} BLE devices found:")
        print("=" * 80)
        
        mopeka_found = False
        for mac, info in sorted(self.devices_found.items()):
            print(f"\nDevice: {mac}")
            print(f"  Name: {info['name']}")
            print(f"  RSSI: {info['rssi']}dBm")
            print(f"  Advertisements: {info['count']}")
            
            if info['manufacturer_data']:
                print(f"  Manufacturer Data:")
                for mfg_id, data in info['manufacturer_data'].items():
                    mfg_name = "MOPEKA" if mfg_id == MOPEKA_MANUFACTURE_ID else f"0x{mfg_id:04X}"
                    print(f"    {mfg_name}: {data}")
                    if mfg_id == MOPEKA_MANUFACTURE_ID:
                        mopeka_found = True
                        
            if info['service_data']:
                print(f"  Service Data:")
                for service_uuid, data in info['service_data'].items():
                    print(f"    {service_uuid}: {data}")
                    
            if info['services']:
                print(f"  Services: {', '.join(info['services'])}")
        
        if not mopeka_found:
            print(f"\n❌ No Mopeka devices (manufacturer ID 0x{MOPEKA_MANUFACTURE_ID:04X}) found.")
            print("   Possible solutions:")
            print("   1. Press and hold the sync button on your Mopeka sensor")
            print("   2. Check sensor battery level")
            print("   3. Move closer to the sensor")
            print("   4. Try running with sudo for enhanced permissions")
        else:
            print(f"\n✅ Mopeka devices were found! Check the detailed output above.")

async def main():
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print("Usage: python debug_ble_scanner_bleak.py [duration_seconds]")
            sys.exit(1)
    else:
        duration = 30
        
    scanner = DebugBLEScanner()
    success = await scanner.scan(duration)
    
    if success:
        scanner.print_summary()
    else:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())