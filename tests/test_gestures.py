"""Packet fixtures, malformed records, transactions, and model restrictions."""

import threading
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from controllers.bluetooth.controller import BTController
from controllers.bluetooth.gestures import (
    build_gesture_request, build_gesture_assignment, parse_gesture_records,
    gesture_capabilities,
)
from controllers.bluetooth.gesture_transport import GestureTransport
from controllers.bluetooth.rcsp import DeviceIdentity, RcspStreamParser


RECORDS = bytes.fromhex("0b 00 02 01 01 03 02 02 03 03 00 08")


def response(opcode, counter, data=b"", status=0, flags=4):
    payload = bytes([status, counter]) + data
    return bytes.fromhex(f"fe dc ba {flags:02x} {opcode:02x} {len(payload):04x}") + payload + b"\xef"


class GestureProtocolTests(unittest.TestCase):
    def test_packets_match_examples_with_only_gesture_config_requested(self):
        self.assertEqual(build_gesture_request(0x42).hex(), "fedcbac4f30003420002ef")
        self.assertEqual(build_gesture_assignment(0x42, 1, "left", 1).hex(),
                         "fedcbac4f20007420500020101ffef")
        self.assertEqual(build_gesture_assignment(0x42, 2, "right", 3).hex(),
                         "fedcbac4f200074205000202ff03ef")
        self.assertEqual(build_gesture_assignment(0x42, 4, "left", 1).hex(),
                         "fedcbac4f20007420500020401ffef")
        self.assertEqual(build_gesture_assignment(0x42, 4, "right", 8).hex(),
                         "fedcbac4f200074205000204ff08ef")

    def test_invalid_command_arguments(self):
        for args in ((256, 1, "left", 1), (1, 5, "left", 1),
                     (1, 1, "both", 1), (1, 1, "left", 255)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                build_gesture_assignment(*args)

    def test_record_order_unknown_configs_partial_gestures_and_unknown_actions(self):
        data = bytes.fromhex("04 00 0a 07 06 05 00 02 03 fe ff 03 12 34 99")
        self.assertEqual(parse_gesture_records(data), {3: (254, 255)})
        self.assertEqual(parse_gesture_records(RECORDS), {1: (1, 3), 2: (2, 3), 3: (0, 8)})
        self.assertEqual(parse_gesture_records(bytes.fromhex("02 00 02")), {})

    def test_malformed_records_are_rejected_as_a_whole(self):
        for data in (b"", b"\0", b"\1\0", RECORDS[:-1], RECORDS + b"\xff",
                     bytes.fromhex("04 00 02 01 01"),
                     bytes.fromhex("08 00 02 01 01 03 01 02 03"),
                     bytes.fromhex("04 00 0a 07 06")):
            with self.subTest(data=data.hex()), self.assertRaises(ValueError):
                parse_gesture_records(data)

    def test_frames_support_every_split_and_coalescing(self):
        frame = response(0xF3, 3, RECORDS)
        for split in range(len(frame) + 1):
            parser = RcspStreamParser()
            packets = parser.feed(frame[:split]) + parser.feed(frame[split:])
            self.assertEqual(len(packets), 1)
            self.assertEqual(parse_gesture_records(packets[0].payload[2:]),
                             {1: (1, 3), 2: (2, 3), 3: (0, 8)})
        self.assertEqual(len(RcspStreamParser().feed(frame + frame)), 2)

    def test_hardware_response_includes_single_tap(self):
        # Redmi Buds 6 Play, 2026-10-26: read-only query captured on RFCOMM 6.
        frame = bytes.fromhex("fe dc ba 04 f3 00 11 00 a0 0e 00 02 04 08 08 01 01 01 02 03 03 03 00 00 ef")
        packet, = RcspStreamParser().feed(frame)
        self.assertEqual(parse_gesture_records(packet.payload[2:]),
                         {4: (8, 8), 1: (1, 1), 2: (3, 3), 3: (0, 0)})

    def test_exact_model_capabilities_and_unknown_identity(self):
        capabilities = gesture_capabilities("Redmi Buds 6 Play")
        self.assertEqual(capabilities, {4: (8, 1, 4, 5, 2, 3, 9), 1: (1, 4, 5, 2, 3, 8),
                                       2: (3, 2, 1, 4, 5, 8), 3: (0, 9, 8)})
        self.assertEqual(gesture_capabilities("Redmi Buds 6"), {})
        self.assertEqual(gesture_capabilities("Redmi Buds 6 Play", DeviceIdentity(0x2717, 20634)), {})
        self.assertEqual(gesture_capabilities("Redmi Buds 6 Play", DeviceIdentity(0xFFFF, 0xFFFF)), {})


class GestureTransportTests(unittest.TestCase):
    def setUp(self):
        self.connection = SimpleNamespace(connected=True, send=Mock())
        self.transport = GestureTransport(self.connection)
        self.records = RECORDS
        self.commands = []

        def send(packet):
            self.commands.append(packet)
            opcode, counter = packet[4], packet[7]
            frame = response(opcode, counter, self.records if opcode == 0xF3 else b"")
            # Exercise the listener path's streaming parser, byte by byte.
            for byte in frame:
                self.transport.feed(bytes([byte]))

        self.connection.send.side_effect = send

    def test_read_and_write_both_sides_verify_with_fresh_counter(self):
        self.assertTrue(self.transport.read().success)
        self.records = bytes.fromhex("0b0002 010103 020203 030008")
        self.assertTrue(self.transport.write(1, "left", 1).success)
        self.assertTrue(self.transport.write(2, "right", 3).success)
        self.assertEqual([packet[4] for packet in self.commands], [0xF3, 0xF2, 0xF3, 0xF2, 0xF3])
        self.assertEqual(self.commands[1][-3:-1], bytes([1, 255]))
        self.assertEqual(self.commands[3][-3:-1], bytes([255, 3]))
        self.assertEqual(len(set(packet[7] for packet in self.commands)), 5)

    def test_mismatched_and_missing_readback_never_report_success(self):
        for records in (RECORDS, bytes.fromhex("050002 020203")):
            self.records = RECORDS
            self.assertTrue(self.transport.read().success)
            self.records = records
            result = self.transport.write(1, "left", 5)
            self.assertFalse(result.success)
            self.assertIn("did not confirm", result.message)
            before = len(self.commands)
            self.assertFalse(self.transport.write(1, "left", 5).success)
            self.assertEqual(len(self.commands), before)

    def test_acknowledgment_without_readback_is_not_success(self):
        self.assertTrue(self.transport.read().success)
        original = self.connection.send.side_effect
        self.connection.send.side_effect = lambda p: original(p) if p[4] == 0xF2 else None
        result = self.transport.write(1, "left", 1, timeout=0.01)
        self.assertFalse(result.success)
        self.assertIn("verification failed", result.message)

    def test_hardware_f4_notification_does_not_replace_write_ack(self):
        self.assertTrue(self.transport.read().success)
        original = self.connection.send.side_effect

        def send(packet):
            if packet[4] == 0xF2:
                notification = bytes.fromhex(f"fe dc ba c7 f4 00 10 {packet[7]:02x}") + bytes.fromhex("0e0002 040808 010101 020303 030000 ef")
                self.assertFalse(self.transport.feed(notification))
            original(packet)

        self.connection.send.side_effect = send
        self.assertTrue(self.transport.write(1, "left", 1).success)

    def test_ignore_wrong_opcode_counter_and_command_frames(self):
        def send(packet):
            counter = packet[7]
            self.transport.feed(response(0xF2, counter, RECORDS))
            self.transport.feed(response(0xF3, (counter + 1) & 255, RECORDS))
            self.transport.feed(response(0xF3, counter, RECORDS, flags=0xC4))
        self.connection.send.side_effect = send
        self.assertFalse(self.transport.read(timeout=0.01).success)

    def test_status_rejection_and_malformed_config(self):
        self.connection.send.side_effect = lambda p: self.transport.feed(response(0xF3, p[7], status=3))
        result = self.transport.read()
        self.assertFalse(result.success)
        self.assertIn("0x03", result.message)
        self.records = RECORDS[:-1]
        self.connection.send.side_effect = lambda p: self.transport.feed(response(0xF3, p[7], self.records))
        self.assertFalse(self.transport.read().success)

    def test_disconnect_cancels_waiter_and_rejects_queued_old_session(self):
        sent = threading.Event()
        self.connection.send.side_effect = lambda _: sent.set()
        generation = self.transport.generation
        results = []
        worker = threading.Thread(target=lambda: results.append(self.transport.read()))
        worker.start()
        self.assertTrue(sent.wait(1))
        self.transport.reset("Disconnected")
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertFalse(results[0].success)
        before = self.connection.send.call_count
        self.assertFalse(self.transport.read(generation=generation).success)
        self.assertEqual(self.connection.send.call_count, before)

    def test_writes_require_device_reported_gesture(self):
        self.assertFalse(self.transport.write(1, "left", 1).success)
        self.assertEqual(self.commands, [])
        self.records = bytes.fromhex("050002 030008")
        self.assertTrue(self.transport.read().success)
        self.assertFalse(self.transport.write(1, "left", 1).success)
        self.assertEqual(len(self.commands), 1)

    def test_failed_send_and_timeout_do_not_poison_next_query(self):
        self.connection.send.side_effect = OSError("Socket closed")
        self.assertFalse(self.transport.read().success)
        self.connection.send.side_effect = lambda p: self.transport.feed(response(0xF3, p[7], RECORDS)[:9])
        self.assertFalse(self.transport.read(timeout=0.01).success)
        self.connection.send.side_effect = lambda p: self.transport.feed(response(0xF3, p[7], RECORDS))
        self.assertTrue(self.transport.read().success)

    def test_counter_wrap_skips_latency_counter(self):
        for initial, expected in ((255, 0), (0x8F, 0x91)):
            self.transport._counter = initial
            self.assertTrue(self.transport.read().success)
            self.assertTrue(self.transport.read().success)
            self.assertEqual(self.commands[-1][7], expected)

    def test_concurrent_reads_are_serialized(self):
        entered = threading.Event()
        self.connection.send.side_effect = lambda _: entered.set()
        results = []
        first = threading.Thread(target=lambda: results.append(self.transport.read(timeout=1)))
        second = threading.Thread(target=lambda: results.append(self.transport.read(timeout=1)))
        first.start()
        self.assertTrue(entered.wait(1))
        second.start()
        self.assertEqual(self.connection.send.call_count, 1)
        self.connection.send.side_effect = lambda p: self.transport.feed(response(0xF3, p[7], RECORDS))
        self.transport.feed(response(0xF3, self.transport._pending.counter, RECORDS))
        first.join(1)
        second.join(1)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.success for result in results))


class GestureControllerTests(unittest.TestCase):
    def test_entrypoint_and_ui_import_in_fresh_processes(self):
        for entrypoint in ("main", "controllers.bluetooth", "ui.components.gestures"):
            with self.subTest(entrypoint=entrypoint):
                result = subprocess.run([sys.executable, "-c", f"import {entrypoint}"],
                                        cwd=Path(__file__).resolve().parents[1],
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_controller_restricts_model_actions_and_side_before_sending(self):
        controller = BTController()
        controller._device_name = "Redmi Buds 6 Play"
        controller._connection.connected = True
        controller._gestures.write = Mock()
        for args in ((1, "left", 7), (3, "left", 6), (1, "both", 1), (5, "left", 1)):
            self.assertFalse(controller.set_gesture_assignment(*args).success)
        controller._gestures.write.assert_not_called()
        controller._device_name = "Other earbuds"
        self.assertFalse(controller.request_gesture_settings().success)

    def test_existing_listener_feeds_gesture_transaction(self):
        controller = BTController()
        controller._device_name = "Redmi Buds 6 Play"
        controller._connection.connected = True

        def send(packet):
            controller._connection.receive = Mock(return_value=response(0xF3, packet[7], RECORDS))
            controller._process_data(0)

        controller._connection.send = Mock(side_effect=send)
        result = controller.request_gesture_settings()
        self.assertTrue(result.success)
        self.assertEqual(result.assignments[2], (2, 3))


if __name__ == "__main__":
    unittest.main()
