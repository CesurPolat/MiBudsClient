"""Both discovery backends must select only the supported connected model."""

import json
import unittest
from unittest.mock import patch

from bluetooth.discovery import BluetoothDiscovery


class DiscoveryTests(unittest.TestCase):
    def test_windows_skips_other_connected_devices(self):
        data = [
            {"Name": "Bluetooth Keyboard", "Address": "112233445566"},
            {"Name": "Redmi Buds 6", "Address": "112233445577"},
            {"Name": "Redmi Buds 6 Play", "Address": "AABBCCDDEEFF"},
        ]
        device = BluetoothDiscovery._parse_output_win(json.dumps(data))
        self.assertEqual(device.name, "Redmi Buds 6 Play")
        self.assertEqual(device.address, "AA:BB:CC:DD:EE:FF")

    def test_windows_requires_matching_name_and_address(self):
        for data in (
            {"Name": "Keyboard", "Address": "112233445566"},
            {"Name": "Redmi Buds 6 Play", "Address": ""}, [], None,
        ):
            with self.subTest(data=data):
                self.assertIsNone(BluetoothDiscovery._parse_output_win(json.dumps(data)))

    def test_name_matching_tolerates_case_and_outer_whitespace_only(self):
        self.assertTrue(BluetoothDiscovery._is_supported_device(" redmi buds 6 PLAY "))
        for name in ("Redmi Buds 6 Play Pro", "My Redmi Buds 6 Play", None):
            self.assertFalse(BluetoothDiscovery._is_supported_device(name))

    def test_linux_skips_other_models_before_querying_connection(self):
        devices = "Device 11:22:33:44:55:66 Keyboard\nDevice AA:BB:CC:DD:EE:FF Redmi Buds 6 Play\n"
        with patch("bluetooth.discovery.subprocess.check_output", side_effect=[devices, "Connected: yes"]) as run:
            device = BluetoothDiscovery._get_connected_device_linux()
        self.assertEqual(device.address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(run.call_args.args[0], ["bluetoothctl", "info", "AA:BB:CC:DD:EE:FF"])
        self.assertEqual(run.call_count, 2)

    def test_linux_does_not_select_disconnected_target(self):
        with patch("bluetooth.discovery.subprocess.check_output", side_effect=[
            "Device AA:BB:CC:DD:EE:FF Redmi Buds 6 Play", "Connected: no",
        ]):
            self.assertIsNone(BluetoothDiscovery._get_connected_device_linux())
