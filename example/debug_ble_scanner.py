#!/usr/bin/env python3
"""
Debug BLE scanner - shows all BLE advertisements to help troubleshoot Mopeka detection.
"""
import sys
import asyncio
import logging
import simplepyble
from mopeka_pro_check.advertisement import MOPEKA_MANUFACTURE_ID

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DebugBLEScanner:
    def __init__(self, adapter_index=0):
        self.adapter_index = adapter_index
        self.adapter = None
        self.devices_found = {}
        self.advertisement_count = 0
        
    def setup_adapter(self):
        """Initialize the BLE adapter"""
        adapters = simplepyble.Adapter.get_adapters()
        if not adapters:
            logger.error("No BLE adapters found")
            return False
            
        if self.adapter_index >= len(adapters):
            logger.error(f"Adapter index {self.adapter_index} out of range. Available: {len(adapters)}")
            return False
            
        self.adapter = adapters[self.adapter_index]
        logger.info(f"Using adapter: {self.adapter.identifier()} [{self.adapter.address()}]")
        return True
        
    def advertisement_callback(self, peripheral):
        """Callback for each BLE advertisement received"""
        try:
            self.advertisement_count += 1
            
            # Get basic info
            mac_address = peripheral.address()
            rssi = peripheral.rssi()
            name = peripheral.identifier() if peripheral.identifier() else "Unknown"
            
            # Store device info
            if mac_address not in self.devices_found:
                self.devices_found[mac_address] = {
                    'name': name,
                    'rssi': rssi,
                    'count': 0,
                    'manufacturer_data': {},
                    'available_methods': []
                }
            
            device_info = self.devices_found[mac_address]
            device_info['count'] += 1
            device_info['rssi'] = rssi  # Update with latest RSSI
            
            # Debug: show available methods on first device
            if self.advertisement_count == 1:
                methods = [m for m in dir(peripheral) if not m.startswith('_')]
                device_info['available_methods'] = methods
                print(f"🔧 Peripheral API methods: {methods}")
            
            # Check manufacturer data
            try:
                manufacturer_data = peripheral.manufacturer_data()
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
            except Exception as e:
                logger.debug(f"No manufacturer data for {mac_address}: {e}")
                    
            # Print every 10th advertisement for progress
            if self.advertisement_count % 10 == 0:
                print(f"📡 Processed {self.advertisement_count} advertisements from {len(self.devices_found)} unique devices")
                
        except Exception as e:
            logger.error(f"Error processing advertisement: {e}")
            
    async def scan(self, duration=30):
        """Start scanning for the specified duration"""
        if not self.setup_adapter():
            return False
            
        print(f"🔍 Starting debug BLE scan for {duration} seconds...")
        print(f"   Looking for Mopeka manufacturer ID: 0x{MOPEKA_MANUFACTURE_ID:04X}")
        print(f"   Will show all BLE devices found\n")
        
        # Set up callback
        self.adapter.set_callback_on_scan_found(self.advertisement_callback)
        
        try:
            self.adapter.scan_start()
            
            # Scan for the specified duration
            await asyncio.sleep(duration)
            
        except Exception as e:
            logger.error(f"Error during scanning: {e}")
            
        finally:
            if self.adapter.scan_is_active():
                self.adapter.scan_stop()
                
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
                        
            if info.get('available_methods'):
                print(f"  Available methods: {', '.join(info['available_methods'])}")
        
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
            print("Usage: python debug_ble_scanner.py [duration_seconds]")
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