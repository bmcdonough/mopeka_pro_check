```shell
(.venv) wrmcd@bosgame:~/github/bmcdonough/mopeka_pro_check$ /home/wrmcd/github/bmcdonough/mopeka_pro_check/.venv/bin/pyt
hon3 /home/wrmcd/github/bmcdonough/mopeka_pro_check/example/debug_ble_scanner.py 60
2025-06-19 22:19:08,464 - INFO - Using adapter: hci0 [90:09:DF:03:E9:E9]
🔍 Starting debug BLE scan for 60 seconds...
   Looking for Mopeka manufacturer ID: 0x0059
   Will show all BLE devices found

🔧 Peripheral API methods: ['address', 'address_type', 'connect', 'descriptor_read', 'descriptor_write', 'disconnect', 'identifier', 'indicate', 'initialized', 'is_connectable', 'is_connected', 'is_paired', 'manufacturer_data', 'mtu', 'notify', 'read', 'rssi', 'services', 'set_callback_on_connected', 'set_callback_on_disconnected', 'tx_power', 'unpair', 'unsubscribe', 'write_command', 'write_request']






✅ Scan completed!
   Total advertisements: 3
   Unique devices: 3

📋 Summary of 3 BLE devices found:
================================================================================

Device: 04:87:27:D9:23:81
  Name: Wyze Lock
  RSSI: -83dBm
  Advertisements: 1
  Manufacturer Data:
    0x4459: 048727d92381000a00
  Available methods: address, address_type, connect, descriptor_read, descriptor_write, disconnect, identifier, indicate, initialized, is_connectable, is_connected, is_paired, manufacturer_data, mtu, notify, read, rssi, services, set_callback_on_connected, set_callback_on_disconnected, tx_power, unpair, unsubscribe, write_command, write_request

Device: 52:F7:85:DE:F7:A0
  Name: Unknown
  RSSI: -81dBm
  Advertisements: 1
  Manufacturer Data:
    0x004C: 10052a988e36e3

Device: 5A:71:D7:D3:E2:6C
  Name: Unknown
  RSSI: -76dBm
  Advertisements: 1
  Manufacturer Data:
    0x004C: 0100000000080000000000000000000000

❌ No Mopeka devices (manufacturer ID 0x0059) found.
   Possible solutions:
   1. Press and hold the sync button on your Mopeka sensor
   2. Check sensor battery level
   3. Move closer to the sensor
   4. Try running with sudo for enhanced permissions
```
