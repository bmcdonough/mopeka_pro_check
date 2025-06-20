#!/usr/bin/env python3
"""
Advanced Mopeka sensor finder using bleak - looks for potential Mopeka devices using multiple detection methods.
"""
import sys
import asyncio
import logging
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from mopeka_pro_check.advertisement import MOPEKA_MANUFACTURE_ID, GAP_MFG_DATA

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MopekaFinder:
    def __init__(self, adapter="hci0"):
        self.adapter = adapter
        self.scanner = None
        self.all_devices = {}
        self.potential_mopeka = {}
        self.advertisement_count = 0
        
    def is_potential_mopeka(self, device: BLEDevice, advertisement_data: AdvertisementData):
        """Check if this device could be a Mopeka sensor using various heuristics"""
        reasons = []
        mac_address = device.address
        name = advertisement_data.local_name or device.name
        manufacturer_data = advertisement_data.manufacturer_data or {}
        
        # Check 1: Exact manufacturer ID match
        if MOPEKA_MANUFACTURE_ID in manufacturer_data:
            reasons.append(f"Exact Mopeka manufacturer ID (0x{MOPEKA_MANUFACTURE_ID:04X})")
        
        # Check 2: Name contains "mopeka" (case insensitive)
        if name and "mopeka" in name.lower():
            reasons.append("Name contains 'Mopeka'")
            
        # Check 3: Look for manufacturer data with 10-byte payloads (typical Mopeka size)
        for mfg_id, data in manufacturer_data.items():
            if len(data) == 10:
                reasons.append(f"10-byte manufacturer data (mfg_id: 0x{mfg_id:04X})")
                
        # Check 4: Look for specific data patterns that might indicate Mopeka
        for mfg_id, data in manufacturer_data.items():
            # Look for patterns that might be Mopeka hardware IDs
            if len(data) >= 1:
                hw_id = data[0]
                if hw_id in [0x03, 0x04, 0x05, 0x0C]:  # Known Mopeka hardware IDs
                    reasons.append(f"Potential Mopeka hardware ID: 0x{hw_id:02X}")
                    
        # Check 5: MAC address patterns (some manufacturers use specific prefixes)
        mac_prefix = mac_address[:8].upper()  # First 3 bytes
        known_mopeka_prefixes = []  # Add known prefixes if we discover them
        if mac_prefix in known_mopeka_prefixes:
            reasons.append(f"Known Mopeka MAC prefix: {mac_prefix}")
            
        return reasons
        
    def advertisement_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        """Callback for each BLE advertisement received"""
        try:
            self.advertisement_count += 1
            
            # Get basic info
            mac_address = device.address
            rssi = advertisement_data.rssi if advertisement_data.rssi is not None else -999
            name = advertisement_data.local_name or device.name
            
            # Get manufacturer data
            manufacturer_data = advertisement_data.manufacturer_data or {}
            
            # Store all device info
            if mac_address not in self.all_devices:
                self.all_devices[mac_address] = {
                    'name': name,
                    'rssi': rssi,
                    'count': 0,
                    'manufacturer_data': manufacturer_data,
                    'first_seen': self.advertisement_count
                }
            
            device_info = self.all_devices[mac_address]
            device_info['count'] += 1
            device_info['rssi'] = rssi  # Update with latest RSSI
            device_info['manufacturer_data'].update(manufacturer_data)
            
            # Check if this could be a Mopeka device
            reasons = self.is_potential_mopeka(device, advertisement_data)
            
            if reasons:
                print(f"\n🔍 POTENTIAL MOPEKA DEVICE:")
                print(f"   MAC: {mac_address}")
                print(f"   Name: {name or 'Unknown'}")
                print(f"   RSSI: {rssi}dBm")
                print(f"   Reasons: {', '.join(reasons)}")
                
                if manufacturer_data:
                    print(f"   Manufacturer Data:")
                    for mfg_id, data in manufacturer_data.items():
                        print(f"     0x{mfg_id:04X}: {data.hex()} ({len(data)} bytes)")
                        
                self.potential_mopeka[mac_address] = {
                    'device_info': device_info,
                    'reasons': reasons
                }
                
            # Print progress every 20 advertisements
            if self.advertisement_count % 20 == 0:
                print(f"📡 Scanned {self.advertisement_count} advertisements, {len(self.all_devices)} unique devices, {len(self.potential_mopeka)} potential Mopeka")
                
        except Exception as e:
            logger.error(f"Error processing advertisement: {e}")
            
    async def scan(self, duration=60):
        """Start scanning for the specified duration"""
        print(f"🔍 Starting advanced Mopeka scan for {duration} seconds...")
        print(f"   Will check for multiple Mopeka indicators")
        print(f"   Press and hold the sync button on your Mopeka sensor for best results\n")
        
        try:
            self.scanner = BleakScanner(
                detection_callback=self.advertisement_callback,
                adapter=self.adapter
            )
            
            await self.scanner.start()
            
            # Scan for the specified duration
            for i in range(duration):
                await asyncio.sleep(1)
                if (i + 1) % 10 == 0:
                    print(f"⏱️  {duration - i - 1} seconds remaining...")
            
        except Exception as e:
            logger.error(f"Error during scanning: {e}")
            return False
            
        finally:
            if self.scanner:
                await self.scanner.stop()
                
        print(f"\n✅ Scan completed!")
        print(f"   Total advertisements: {self.advertisement_count}")
        print(f"   Unique devices: {len(self.all_devices)}")
        print(f"   Potential Mopeka devices: {len(self.potential_mopeka)}")
        return True
        
    def print_results(self):
        """Print detailed results"""
        if self.potential_mopeka:
            print(f"\n🎯 Found {len(self.potential_mopeka)} potential Mopeka device(s):")
            print("=" * 80)
            
            for mac, info in self.potential_mopeka.items():
                device = info['device_info']
                reasons = info['reasons']
                
                print(f"\nDevice: {mac}")
                print(f"  Name: {device['name'] or 'Unknown'}")
                print(f"  RSSI: {device['rssi']}dBm")
                print(f"  Advertisement Count: {device['count']}")
                print(f"  Detection Reasons: {', '.join(reasons)}")
                
                if device['manufacturer_data']:
                    print(f"  Manufacturer Data:")
                    for mfg_id, data in device['manufacturer_data'].items():
                        mfg_name = "MOPEKA" if mfg_id == MOPEKA_MANUFACTURE_ID else f"0x{mfg_id:04X}"
                        print(f"    {mfg_name}: {data.hex()} ({len(data)} bytes)")
                        
                        # Try to decode if it looks like Mopeka data
                        if mfg_id == MOPEKA_MANUFACTURE_ID or len(data) == 10:
                            try:
                                print(f"    Attempting to decode as Mopeka data:")
                                if len(data) >= 1:
                                    print(f"      Hardware ID: 0x{data[0]:02X}")
                                if len(data) >= 2:
                                    battery_raw = data[1] & 0x7F
                                    battery_voltage = battery_raw / 32.0
                                    print(f"      Battery: {battery_voltage:.2f}V")
                                if len(data) >= 3:
                                    sync_pressed = bool(data[2] & 0x80)
                                    temp_raw = data[2] & 0x7F
                                    temp_celsius = temp_raw - 40
                                    print(f"      Sync Button: {'Pressed' if sync_pressed else 'Not pressed'}")
                                    print(f"      Temperature: {temp_celsius}°C")
                            except Exception as e:
                                print(f"    Decode failed: {e}")
        else:
            print(f"\n❌ No potential Mopeka devices found.")
            
        print(f"\n📊 All {len(self.all_devices)} BLE devices found:")
        print("-" * 40)
        for mac, device in sorted(self.all_devices.items()):
            mfg_ids = list(device['manufacturer_data'].keys()) if device['manufacturer_data'] else []
            mfg_str = f" (Mfg: {[f'0x{mid:04X}' for mid in mfg_ids]})" if mfg_ids else ""
            print(f"  {mac} - {device['name'] or 'Unknown'} - {device['rssi']}dBm{mfg_str}")

async def main():
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print("Usage: python mopeka_finder_bleak.py [duration_seconds]")
            sys.exit(1)
    else:
        duration = 60
        
    finder = MopekaFinder()
    success = await finder.scan(duration)
    
    if success:
        finder.print_results()
    else:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())