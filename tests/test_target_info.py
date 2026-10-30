"""Target-info wire framing and diagnostic response coverage."""

import unittest
from unittest.mock import Mock

from controllers.bluetooth.controller import BTController
from controllers.bluetooth.rcsp import build_identity_request


class TargetInfoTests(unittest.TestCase):
    def query(self, fields, status=0, fragmented=False):
        controller = BTController()
        controller._ensure_connected = Mock(return_value=True)
        sent = []

        def respond(command):
            sent.append(command)
            payload = bytes([status, command[7]]) + fields
            frame = bytes.fromhex("fe dc ba 00 02") + len(payload).to_bytes(2, "big") + payload + b"\xef"
            # A stale response and a command echo must not finish the request.
            controller._process_identity_data(command)
            stale = bytearray(frame)
            stale[8] = (command[7] - 1) & 255
            controller._process_identity_data(bytes(stale))
            if fragmented:
                for byte in frame:
                    controller._process_identity_data(bytes([byte]))
            else:
                controller._process_identity_data(frame)

        controller._connection.send = respond
        results = [controller.request_device_identity(timeout=0.1) for _ in range(2)]
        self.assertNotEqual(sent[0][7], sent[1][7])
        return results

    def test_exact_read_only_request(self):
        self.assertEqual(build_identity_request(1), bytes.fromhex("FE DC BA C4 02 00 05 01 FF FF FF FF EF"))

    def test_fragmented_response_preserves_entire_frame(self):
        for success, text in self.query(bytes.fromhex("05 03 27 17 50 9B"), fragmented=True):
            self.assertTrue(success)
            self.assertIn("05 03 27 17 50 9B EF", text)
            self.assertIn("RX: FE DC BA 00 02 00 08 00", text)

    def test_unknown_fields_and_rejection_still_expose_hex(self):
        for fields, status in [(bytes.fromhex("02 99 01"), 0), (b"", 3)]:
            for success, text in self.query(fields, status):
                self.assertFalse(success)
                self.assertIn("RX: FE DC BA 00 02", text)
                self.assertTrue(text.endswith(" EF"))
