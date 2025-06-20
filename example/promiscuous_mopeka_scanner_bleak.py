#!/usr/bin/env python3
"""
Promiscuous BLE scanner for Mopeka beacons using bleak.
Captures all BLE advertisements and filters for Mopeka manufacturer data.
"""
import sys
import asyncio
import logging
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from mopeka_pro_check.advertisement import MOPEKA_MANUFACTURE_ID, MopekaAdvertisement, GAP_MFG_DATA

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PromiscuousMopekaScanner:
    def __init__(self, adapter="hci0"):
        self.adapter = adapter
        self.scanner = None
        self.mopeka_devices_found = {}
        
    def advertisement_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        """Callback for each BLE advertisement received"""
        try:
            # Get basic info
            mac_address = device.address
            rssi = advertisement_data.rssi if advertisement_data.rssi is not None else -999
            name = advertisement_data.local_name or device.name
            
            # Check manufacturer data
            manufacturer_data = advertisement_data.manufacturer_data
            
            if not manufacturer_data:
                return
                
            # Look for Mopeka manufacturer ID
            mopeka_payload = manufacturer_data.get(MOPEKA_MANUFACTURE_ID)
            if mopeka_payload:
                logger.info(f"Found Mopeka device: {mac_address} RSSI: {rssi}dBm Name: {name}")
                logger.info(f"Manufacturer data: {mopeka_payload.hex()}")
                
                try:
                    # Reconstruct the full manufacturer data as expected by MopekaAdvertisement
                    # Format: [GAP_TYPE (0xFF), MFG_ID_LSB (0x59), MFG_ID_MSB (0x00), payload...]
                    full_mfg_data = bytes([GAP_MFG_DATA, 0x59, 0x00]) + mopeka_payload
                    
                    # Parse the Mopeka advertisement
                    ad = MopekaAdvertisement(mac_address, rssi, name, full_mfg_data)
                    self.mopeka_devices_found[mac_address] = ad
                    
                    logger.info(f"Parsed Mopeka advertisement:")
                    logger.info(f"  {ad}")
                    
                except Exception as e:
                    logger.error(f"Failed to parse Mopeka advertisement from {mac_address}: {e}")
                    logger.info(f"Raw manufacturer data: {mopeka_payload.hex()}")
            
            # Also check for other manufacturer data that might be Mopeka with different structure
            for mfg_id, data in manufacturer_data.items():
                if mfg_id != MOPEKA_MANUFACTURE_ID and len(data) >= 10:
                    logger.debug(f"Device {mac_address}: Unknown manufacturer {mfg_id:04X} with {len(data)} bytes: {data.hex()}")
                    
        except Exception as e:
            logger.error(f"Error processing advertisement: {e}")
            
    async def scan(self, duration=30):
        """Start promiscuous scanning for the specified duration"""
        logger.info(f"Starting promiscuous scan for {duration} seconds...")
        logger.info(f"Looking for Mopeka manufacturer ID: 0x{MOPEKA_MANUFACTURE_ID:04X}")
        
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
            
        logger.info(f"Scan completed. Found {len(self.mopeka_devices_found)} Mopeka devices.")
        return True
        
    def print_summary(self):
        """Print summary of found devices"""
        if not self.mopeka_devices_found:
            print("\nNo Mopeka devices found.")
            print("Possible issues:")
            print("1. Sensors are not transmitting (check battery)")
            print("2. Sensors are too far away")
            print("3. Bluetooth adapter permissions issue")
            print("4. Sensors in sleep mode")
            return
            
        print(f"\n=== Found {len(self.mopeka_devices_found)} Mopeka devices ===")
        for mac, ad in self.mopeka_devices_found.items():
            print(f"\nDevice: {mac}")
            ad.Dump()

async def main():
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print("Usage: python promiscuous_mopeka_scanner_bleak.py [duration_seconds]")
            sys.exit(1)
    else:
        duration = 30
        
    scanner = PromiscuousMopekaScanner()
    success = await scanner.scan(duration)
    
    if success:
        scanner.print_summary()
    else:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())