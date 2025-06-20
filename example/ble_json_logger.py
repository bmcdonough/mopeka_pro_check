#!/usr/bin/env python3
"""
Mopeka BLE JSON Logger - Listens for Mopeka Bluetooth packets using bleak and outputs JSON to stdout.
Outputs one JSON object per line for each Mopeka BLE advertisement received.
Runs indefinitely until interrupted (Ctrl+C).
"""
import sys
import asyncio
import json
import logging
from datetime import datetime, timezone
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from mopeka_pro_check.advertisement import MOPEKA_MANUFACTURE_ID, MopekaAdvertisement, GAP_MFG_DATA

# Suppress bleak logging to avoid interfering with JSON output
logging.getLogger("bleak").setLevel(logging.WARNING)

class BLEJSONLogger:
    def __init__(self, adapter="hci0", include_raw=False):
        self.adapter = adapter
        self.scanner = None
        self.packet_count = 0
        self.include_raw = include_raw
        
    def advertisement_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        """Process each Mopeka BLE advertisement and output as JSON"""
        try:
            # Check if this is a Mopeka device first
            manufacturer_data = advertisement_data.manufacturer_data
            if not manufacturer_data or MOPEKA_MANUFACTURE_ID not in manufacturer_data:
                return  # Skip non-Mopeka devices
            
            self.packet_count += 1
            
            # Get basic advertisement info
            mac_address = device.address
            rssi = advertisement_data.rssi if advertisement_data.rssi is not None else None
            name = advertisement_data.local_name or device.name
            timestamp = datetime.utcnow().isoformat() + "Z"
            
            # Get Mopeka manufacturer data
            mopeka_payload = manufacturer_data[MOPEKA_MANUFACTURE_ID]
            
            # Build base JSON object for Mopeka device
            json_obj = {
                "timestamp": timestamp,
                "packet_number": self.packet_count,
                "mac_address": mac_address,
                "rssi": rssi,
                "local_name": name,
                "manufacturer_id": f"0x{MOPEKA_MANUFACTURE_ID:04X}"
            }
            
            # Include raw data only if requested
            if self.include_raw:
                json_obj["raw_manufacturer_data"] = mopeka_payload.hex()
            
            # Process service data if present
            service_data = advertisement_data.service_data
            if service_data:
                json_obj["service_data"] = {}
                for service_uuid, data in service_data.items():
                    json_obj["service_data"][str(service_uuid)] = data.hex()
            
            # Process service UUIDs if present
            service_uuids = advertisement_data.service_uuids
            if service_uuids:
                json_obj["service_uuids"] = [str(uuid) for uuid in service_uuids]
            
            # Attempt to decode Mopeka data
            try:
                # Reconstruct the full manufacturer data as expected by MopekaAdvertisement
                # Format: [GAP_TYPE (0xFF), MFG_ID_LSB (0x59), MFG_ID_MSB (0x00), payload...]
                full_mfg_data = bytes([GAP_MFG_DATA, 0x59, 0x00]) + mopeka_payload
                
                # Parse the Mopeka advertisement
                mopeka_ad = MopekaAdvertisement(mac_address, rssi or -999, name, full_mfg_data)
                
                # Extract all decoded Mopeka data
                json_obj.update({
                    "hardware_id": f"0x{mopeka_ad.HardwareId.value:02X}",
                    "hardware_name": mopeka_ad.HardwareId.name,
                    "battery_voltage": round(mopeka_ad.BatteryVoltage, 3),
                    "battery_percent": mopeka_ad.BatteryPercent,
                    "sync_button_pressed": mopeka_ad.SyncButtonPressed,
                    "temperature_celsius": mopeka_ad.TemperatureInCelsius,
                    "temperature_fahrenheit": round(mopeka_ad.TemperatureInFahrenheit, 1),
                    "tank_level_mm": mopeka_ad.TankLevelInMM,
                    "tank_level_inches": mopeka_ad.TankLevelInInches,
                    "reading_quality_stars": mopeka_ad.ReadingQualityStars,
                    "decode_status": "success"
                })
                
            except Exception as e:
                # If Mopeka decoding fails, include error info and raw data for debugging
                json_obj["decode_status"] = "failed"
                json_obj["decode_error"] = str(e)
                # Always include raw data when decode fails, regardless of include_raw setting
                if not self.include_raw:
                    json_obj["raw_manufacturer_data"] = mopeka_payload.hex()
            
            # Output JSON object to stdout
            print(json.dumps(json_obj, separators=(',', ':')))
            sys.stdout.flush()
            
        except Exception as e:
            # Create error JSON object if something goes critically wrong
            error_obj = {
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "packet_number": self.packet_count,
                "error": f"Failed to process Mopeka advertisement: {str(e)}",
                "mac_address": getattr(device, 'address', 'unknown') if device else 'unknown'
            }
            print(json.dumps(error_obj, separators=(',', ':')))
            sys.stdout.flush()
            
    async def start_logging(self, timeout=None):
        """Start BLE scanning and JSON logging indefinitely or for specified timeout"""
        try:
            self.scanner = BleakScanner(
                detection_callback=self.advertisement_callback,
                adapter=self.adapter
            )
            
            await self.scanner.start()
            
            # Run indefinitely until interrupted or timeout
            try:
                if timeout is not None:
                    await asyncio.sleep(timeout)
                else:
                    while True:
                        await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass
            
        except Exception as e:
            error_obj = {
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "error": f"BLE scanning error: {str(e)}",
                "adapter": self.adapter
            }
            print(json.dumps(error_obj, separators=(',', ':')), file=sys.stderr)
            return False
            
        finally:
            if self.scanner:
                await self.scanner.stop()
                
        return True

async def main():
    adapter = "hci0"
    include_raw = False
    timeout = None
    
    # Parse command line arguments
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--raw" or arg == "-r":
            include_raw = True
        elif arg == "--timeout" or arg == "-t":
            if i + 1 >= len(sys.argv):
                print("Error: --timeout requires a value", file=sys.stderr)
                sys.exit(1)
            try:
                timeout = float(sys.argv[i + 1])
                if timeout <= 0:
                    print("Error: timeout must be a positive number", file=sys.stderr)
                    sys.exit(1)
            except ValueError:
                print(f"Error: invalid timeout value '{sys.argv[i + 1]}'", file=sys.stderr)
                sys.exit(1)
            i += 1  # Skip the timeout value
        elif arg == "--help" or arg == "-h":
            print("Usage: python ble_json_logger.py [options] [adapter]", file=sys.stderr)
            print("Options:", file=sys.stderr)
            print("  --raw, -r           Include raw manufacturer data in JSON output", file=sys.stderr)
            print("  --timeout, -t SEC   Exit cleanly after SEC seconds (default: run forever)", file=sys.stderr)
            print("  --help, -h          Show this help message", file=sys.stderr)
            print("Arguments:", file=sys.stderr)
            print("  adapter             BLE adapter to use (default: hci0)", file=sys.stderr)
            print("", file=sys.stderr)
            print("Examples:", file=sys.stderr)
            print("  python ble_json_logger.py --raw hci1", file=sys.stderr)
            print("  python ble_json_logger.py --timeout 30", file=sys.stderr)
            sys.exit(0)
        elif not arg.startswith("-"):
            adapter = arg
        else:
            print(f"Unknown option: {arg}", file=sys.stderr)
            print("Use --help for usage information", file=sys.stderr)
            sys.exit(1)
        i += 1
    
    # Output startup info to stderr so it doesn't interfere with JSON output
    startup_info = {
        "action": "starting_mopeka_scan",
        "adapter": adapter,
        "include_raw_data": include_raw,
        "timeout_seconds": timeout,
        "mopeka_manufacturer_id": f"0x{MOPEKA_MANUFACTURE_ID:04X}",
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
    }
    print(json.dumps(startup_info), file=sys.stderr)
    
    logger = BLEJSONLogger(adapter, include_raw)
    success = await logger.start_logging(timeout)
    
    # Output completion info to stderr
    completion_info = {
        "action": "mopeka_scan_completed",
        "total_mopeka_packets": logger.packet_count,
        "success": success,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
    }
    print(json.dumps(completion_info), file=sys.stderr)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        completion_info = {
            "action": "mopeka_scan_interrupted",
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
        }
        print(json.dumps(completion_info), file=sys.stderr)
        sys.exit(0)