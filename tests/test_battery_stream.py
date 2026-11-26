"""Preserve battery records across fragmented and coalesced RFCOMM reads."""

import unittest
from unittest.mock import Mock

from controllers.battery.stream import BatteryStreamParser
def battery_frame(values):
    # A target-info response: STATUS/SEQ followed by length/type attributes.
    payload = bytes.fromhex("00 0b 02 06 02") + bytes((len(values) + 1, 7)) + bytes(values)
    return bytes.fromhex("fe dc ba 04 02") + len(payload).to_bytes(2, "big") + payload + bytes.fromhex("ef")

from controllers.bluetooth.controller import BTController


class BatteryStreamTests(unittest.TestCase):
    def test_every_split_position_and_bytewise_delivery(self):
        record = battery_frame([188, 70, 255])
        for split in range(len(record) + 1):
            parser = BatteryStreamParser()
            records = parser.feed(record[:split]) + parser.feed(record[split:])
            self.assertEqual(len(records), 1)
            self.assertEqual((records[0].left, records[0].right, records[0].case), (188, 70, 255))
        parser = BatteryStreamParser()
        records = [item for byte in record for item in parser.feed(bytes([byte]))]
        self.assertEqual(len(records), 1)

    def test_multiple_records_and_noise_are_consumed_exactly_once(self):
        parser = BatteryStreamParser()
        records = parser.feed(b"noise" + battery_frame([60, 70, 80]) + b"noise" + battery_frame([61, 71, 81]))
        self.assertEqual([item.left for item in records], [60, 61])
        self.assertEqual(parser.feed(b""), [])
        parser.feed(b"x" * 100000)
        self.assertLessEqual(parser._parser.buffered_bytes, 2)

    def test_disconnect_reset_prevents_cross_connection_records(self):
        parser = BatteryStreamParser()
        record = battery_frame([60, 70, 80])
        parser.feed(record[:5])
        parser.reset()
        self.assertEqual(parser.feed(record[5:]), [])
        self.assertEqual(len(parser.feed(record)), 1)

    def test_controller_delivers_fragmented_battery_once(self):
        callback = Mock()
        controller = BTController(battery_callback=callback)
        record = battery_frame([60, 70, 80])
        controller._connection.connected = True
        controller._connection.receive = Mock(side_effect=[record[:2], record[2:5], record[5:]])
        size = 0
        for _ in range(3):
            size = controller._process_data(size)
        callback.assert_called_once_with(60, 70, 80)

    def test_controller_resets_partial_battery_on_disconnect(self):
        controller = BTController()
        controller._battery_parser.feed(battery_frame([60, 70, 80])[:10])
        controller._reset_identity_state("Disconnected")
        self.assertEqual(controller._battery_parser.feed(bytes([70, 80])), [])
