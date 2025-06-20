#!/usr/bin/env python3
"""
Promiscuous BLE scanner for Mopeka beacons.
Captures all BLE advertisements and filters for Mopeka manufacturer data.
"""
import sys
import asyncio
import logging
import simplepyble
from mopeka_pro_check.advertisement import MOPEKA_MANUFACTURE_ID, MopekaAdvertisement

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PromiscuousMopekaScanner:
    def __init__(self, adapter_index=0):
        self.adapter_index = adapter_index
        self.adapter = None
        self.running = False
        self.mopeka_devices_found = {}
        
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
            # Get basic info
            mac_address = peripheral.address()
            rssi = peripheral.rssi()
            name = peripheral.identifier() if peripheral.identifier() else None
            
            # Check manufacturer data
            manufacturer_data = peripheral.manufacturer_data()
            
            if not manufacturer_data:
                return
                
            # Look for Mopeka manufacturer ID
            for mfg_id, data in manufacturer_data.items():
                if mfg_id == MOPEKA_MANUFACTURE_ID:
                    logger.info(f"Found Mopeka device: {mac_address} RSSI: {rssi}dBm Name: {name}")
                    logger.info(f"Manufacturer data: {data.hex()}")
                    
                    try:
                        # Reconstruct the full manufacturer data as expected by MopekaAdvertisement
                        # Format: [GAP_TYPE (0xFF), MFG_ID_LSB (0x59), MFG_ID_MSB (0x00), payload...]
                        full_mfg_data = bytes([0xFF, 0x59, 0x00]) + data
                        
                        # Parse the Mopeka advertisement
                        ad = MopekaAdvertisement(mac_address, rssi, name, full_mfg_data)
                        self.mopeka_devices_found[mac_address] = ad
                        
                        logger.info(f"Parsed Mopeka advertisement:")
                        logger.info(f"  {ad}")
                        
                    except Exception as e:
                        logger.error(f"Failed to parse Mopeka advertisement from {mac_address}: {e}")
                        logger.info(f"Raw manufacturer data: {data.hex()}")
                        
                elif len(data) >= 10:  # Could be Mopeka data with different structure
                    logger.debug(f"Device {mac_address}: Unknown manufacturer {mfg_id:04X} with {len(data)} bytes: {data.hex()}")
                    
        except Exception as e:
            logger.error(f"Error processing advertisement: {e}")
            
    async def scan(self, duration=30):
        """Start promiscuous scanning for the specified duration"""
        if not self.setup_adapter():
            return False
            
        logger.info(f"Starting promiscuous scan for {duration} seconds...")
        logger.info(f"Looking for Mopeka manufacturer ID: 0x{MOPEKA_MANUFACTURE_ID:04X}")
        
        # Set up callback
        self.adapter.set_callback_on_scan_found(self.advertisement_callback)
        
        try:
            self.running = True
            self.adapter.scan_start()
            
            # Scan for the specified duration
            await asyncio.sleep(duration)
            
        except Exception as e:
            logger.error(f"Error during scanning: {e}")
            
        finally:
            if self.adapter.scan_is_active():
                self.adapter.scan_stop()
            self.running = False
            
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
            print("Usage: python promiscuous_mopeka_scanner.py [duration_seconds]")
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