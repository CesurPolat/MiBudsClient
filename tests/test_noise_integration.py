import os
import threading
import tempfile
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

from controllers.bluetooth.capabilities import resolve_capabilities
from controllers.bluetooth.config_transport import RcspConfigTransport
from controllers.bluetooth.noise import noise_backend_enabled, noise_capabilities, NoiseState
from controllers.bluetooth.noise_transport import NoiseTransport
from ui.components.settings_card import SettingsCard
from controllers.bluetooth.noise_capture import record


MODEL = "miwear.headphone.n76g"


class NoiseIntegrationTests(unittest.TestCase):
    def test_capture_is_explicit_local_and_directional(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "capture.jsonl"
            with patch.dict(os.environ, {"MIBUDS_ANC_CAPTURE": ""}):
                record("TX", b"\x01")
                self.assertFalse(path.exists())
            with patch.dict(os.environ, {"MIBUDS_ANC_CAPTURE": str(path)}):
                record("SESSION", model=MODEL, channel=24)
                record("RX", bytes.fromhex("fe dc ba"))
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(rows[0]["model"], MODEL)
            self.assertEqual(rows[1]["direction"], "RX")
            self.assertEqual(rows[1]["hex"], "FE DC BA")

    def test_function_list_visibility_without_opt_in(self):
        with patch.dict(os.environ, {"MIBUDS_EXPERIMENTAL_ANC": ""}):
            self.assertTrue(noise_backend_enabled(resolve_capabilities("Redmi Buds 5 Pro")))
            self.assertFalse(noise_backend_enabled(resolve_capabilities("Redmi Buds 6 Play")))
            self.assertTrue(noise_backend_enabled(resolve_capabilities("Redmi Buds 6 Pro")))
            card = SettingsCard()
            card.set_capabilities(resolve_capabilities("Redmi Buds 5 Pro"))
            card.update_connection_state("connected")
            self.assertTrue(card.noise.visible)
            self.assertIn(card.noise, card.content.controls)
            card.set_capabilities(resolve_capabilities("Redmi Buds 6 Play"))
            self.assertFalse(card.noise.visible)

    def test_full_transport_matches_sequence_and_reads_back(self):
        connection = SimpleNamespace(connected=True)
        channel = RcspConfigTransport(connection)
        sent = []

        def send(frame):
            sent.append(frame)
            opcode, seq = frame[4], frame[7]
            data = bytes.fromhex("04 00 0b 01 02") if opcode == 0xF3 else b""
            # Wrong SEQ must not complete pending request; split the valid frame.
            def receive():
                def response(counter):
                    body = bytes((0, counter)) + data
                    return bytes.fromhex("fe dc ba 04") + bytes((opcode,)) + len(body).to_bytes(2, "big") + body + b"\xef"
                channel.feed(response((seq + 1) & 255))
                valid = response(seq)
                channel.feed(valid[:6])
                channel.feed(valid[6:])
            threading.Thread(target=receive).start()

        connection.send = send
        state = NoiseTransport(channel).apply(noise_capabilities(resolve_capabilities("Redmi Buds 5 Pro")),
                                              channel.generation, 1, 2, timeout=1)
        self.assertEqual(state, NoiseState(1, 2))
        self.assertEqual([frame[4] for frame in sent], [0xF2, 0xF3])

    def test_disconnect_cancels_pending_transaction(self):
        sent = threading.Event()
        channel = RcspConfigTransport(SimpleNamespace(connected=True, send=lambda _: sent.set()))
        errors = []
        def read():
            try:
                NoiseTransport(channel).read(channel.generation, timeout=1)
            except OSError as exc:
                errors.append(exc)
        worker = threading.Thread(target=read)
        worker.start()
        self.assertTrue(sent.wait(1))
        channel.reset("disconnected")
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(errors), 1)

    def test_ui_requires_read_and_ignores_old_results(self):
        with patch.dict(os.environ, {"MIBUDS_EXPERIMENTAL_ANC": ""}):
            action = Mock()
            card = SettingsCard(on_noise_action=action)
            card.set_capabilities(resolve_capabilities("Redmi Buds 5 Pro"))
            card.update_connection_state("connected")
            panel = card.noise
            self.assertTrue(panel.mode.disabled)
            token = panel.begin("read", 4)
            panel.complete(token, NoiseState(1, 0))
            self.assertFalse(panel.mode.disabled)
            self.assertEqual([opt.key for opt in panel.level.options], ["1", "0", "2"])
            panel.notification(3, NoiseState(2, 0))
            self.assertEqual(panel.mode.value, "1")
            panel.notification(4, NoiseState(2, 0))
            self.assertEqual(panel.mode.value, "2")
            old = panel.begin("write", 4)
            card.update_connection_state("disconnected")
            panel.complete(old, NoiseState(1, 2))
            self.assertIsNone(panel._state)
