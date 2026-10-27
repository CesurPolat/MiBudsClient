"""EQ packet fixtures, shared transactions and Flet state without hardware."""
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from controllers.bluetooth.controller import BTController
from controllers.bluetooth.equalizer import (
    EqBand, EqState, EqResult, build_eq_request, build_profile, build_custom_mode,
    build_custom_eq, build_eq_reset, parse_custom_eq, parse_profile, eq_profiles,
)
from controllers.bluetooth.eq_transport import EqTransport
from controllers.bluetooth.gesture_transport import GestureTransport
from controllers.bluetooth.rcsp import DeviceIdentity
from controllers.bluetooth.rcsp import RcspStreamParser
from ui.components.equalizer import EqualizerSettings
from ui.app_message_handler import AppMessageHandler
from utils.i18n import message as m, set_language, t


def record(config, value):
    return bytes([len(value) + 2]) + config.to_bytes(2, "big") + value


def custom_record(bands=(EqBand(1000, -3), EqBand(8000, 2)), mode=10, bound=10, name=b""):
    value = bytes([1, mode, bound, 0, 1, len(name)]) + name + bytes([len(bands)])
    for b in bands:
        value += b.frequency.to_bytes(2, "big") + bytes([b.gain if b.gain >= 0 else 128 - b.gain])
    return record(55, value)


def response(opcode, ss, data=b"", status=0, flags=4):
    body = bytes([status, ss]) + data
    return bytes.fromhex(f"fe dc ba {flags:02x} {opcode:02x} {len(body):04x}") + body + b"\xef"


class EqCodecTests(unittest.TestCase):
    def test_reference_packets(self):
        self.assertEqual(build_eq_request(0x42, 7).hex(), "fedcbac4f30003420007ef")
        self.assertEqual(build_eq_request(0x42, 55).hex(), "fedcbac4f30003420037ef")
        self.assertEqual(build_profile(0x42, 5).hex(), "fedcbac4f200054203000705ef")
        self.assertEqual(build_custom_mode(0x42, 10).hex(), "fedcbac4f2000642040037010aef")
        self.assertEqual(build_eq_reset(0x42).hex(), "fedcbac4f200084206003704010101ef")

    def test_dynamic_lengths_and_sign_magnitude(self):
        for count in (1, 3, 10, 81):
            bands = tuple(EqBand(1000 + i, -3) for i in range(count))
            for preview in (False, True):
                packet = build_custom_eq(3, bands, 10, preview=preview)
                self.assertEqual(int.from_bytes(packet[5:7], "big"), (8 if preview else 11) + 3 * count)
                self.assertEqual(packet[8], (6 if preview else 9) + 3 * count)
                self.assertEqual(packet[-4:-1], (1000 + count - 1).to_bytes(2, "big") + b"\x83")
        self.assertEqual(build_custom_eq(3, (EqBand(1000, -10),), 10)[-4:-1], bytes.fromhex("03e88a"))

    def test_read_order_name_and_zero_bound(self):
        bands = (EqBand(8000, 3), EqBand(1000, -3), EqBand(60, -10))
        custom = parse_custom_eq(custom_record(bands, bound=0, name=b"test"))
        self.assertEqual(custom.bands, bands)
        self.assertEqual(custom.bound, 10)
        self.assertEqual(custom.name, b"test")
        self.assertEqual(parse_profile(record(99, b"x") + record(7, b"\x06")), 6)

    def test_invalid_data_and_arguments(self):
        valid = custom_record()
        for data in (b"", valid[:-1], valid + valid, record(55, bytes.fromhex("010a0a0001ff02")),
                     custom_record((), bound=10), custom_record((EqBand(0, 0),)),
                     custom_record((EqBand(1000, 11),)), record(7, b"\x00")):
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_custom_eq(data)
        for band in (EqBand(1000, -11), EqBand(0, 0), EqBand(70000, 0), EqBand(1000, 1.5)):
            with self.assertRaises(ValueError):
                build_custom_eq(1, (band,), 10)
        with self.assertRaises(ValueError):
            build_custom_eq(1, (EqBand(1000, 0),) * 82, 10)
        with self.assertRaises(ValueError):
            build_profile(1, 2)
        with self.assertRaises(ValueError):
            build_eq_request(256, 7)

    def test_model_catalog_limits_profiles(self):
        self.assertEqual(eq_profiles("Redmi Buds 6 Play"), (0, 6, 5, 1, 7))
        self.assertEqual(eq_profiles("Redmi Buds 6"), ())
        self.assertEqual(eq_profiles("Redmi Buds 6 Play", DeviceIdentity(0xffff, 0xffff)), ())
        controller = BTController()
        controller._equalizer.apply = Mock()
        self.assertFalse(controller.apply_eq("profile", profile=2).success)
        controller._equalizer.apply.assert_not_called()

    def test_hardware_readback_2026_10_27(self):
        # Redmi Buds 6 Play on RFCOMM 6: Vocal is active; 0037 has no band data.
        frames = bytes.fromhex("fedcba04f3000600a003000701ef fedcba04f3000600a103003700ef")
        preset, custom = RcspStreamParser().feed(frames)
        self.assertEqual(parse_profile(preset.payload[2:]), 1)
        with self.assertRaises(ValueError):
            parse_custom_eq(custom.payload[2:])


class EqTransactionTests(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.connection = SimpleNamespace(connected=True, send=Mock())
        self.channel = GestureTransport(self.connection)
        self.eq = EqTransport(self.channel)
        self.profile = 0
        self.bands = (EqBand(1000, -3), EqBand(8000, 2))
        self.custom_data = custom_record(self.bands)
        self.commands = []
        self.connection.send.side_effect = self.send

    def send(self, packet):
        self.commands.append(packet)
        opcode, ss = packet[4], packet[7]
        config = int.from_bytes(packet[8:10] if opcode == 0xF3 else packet[9:11], "big")
        data = b""
        if opcode == 0xF3:
            data = record(7, bytes([self.profile])) if config == 7 else self.custom_data
            if config == 2:
                data = bytes.fromhex("05 00 02 01 01 03")
        elif config == 7:
            self.profile = packet[11]
        frame = response(opcode, ss, data)
        for byte in frame:
            self.channel.feed(bytes([byte]))

    def test_partial_support_preserves_profiles(self):
        self.custom_data = b""
        result = self.eq.read(timeout=0.01)
        self.assertTrue(result.success)
        self.assertEqual(result.state.profile, 0)
        self.assertIsNone(result.state.custom)
        self.assertTrue(self.eq.apply("profile", profile=5).success)
        self.assertFalse(self.eq.apply("save", bands=self.bands).success)

    def test_preview_is_not_saved_and_save_requires_matching_readback(self):
        self.assertTrue(self.eq.read().success)
        result = self.eq.apply("preview", bands=self.bands)
        self.assertTrue(result.success)
        self.assertIn("Preview", result.message)
        self.assertEqual(self.commands[-1][11:14], b"\x05\x01\x01")
        self.assertTrue(self.eq.apply("save", bands=self.bands).success)
        altered = (EqBand(1000, 4), EqBand(8000, 2))
        self.assertFalse(self.eq.apply("save", bands=altered).success)
        sent = len(self.commands)
        self.assertFalse(self.eq.apply("save", bands=self.bands).success)
        self.assertEqual(len(self.commands), sent)

    def test_reset_and_frequency_order_validation(self):
        self.assertTrue(self.eq.read().success)
        self.assertFalse(self.eq.apply("save", bands=self.bands[::-1]).success)
        self.eq.read()
        self.custom_data = custom_record(tuple(EqBand(b.frequency, 0) for b in self.bands))
        self.assertTrue(self.eq.apply("reset").success)

    def test_wrong_ss_opcode_config_and_commands_are_ignored(self):
        def send(packet):
            ss = packet[7]
            wrong = record(99, b"\x00")
            for frame in (response(0xF3, (ss + 1) & 255, record(7, b"\x00")),
                          response(0xF2, ss), response(0xF3, ss, wrong),
                          response(0xF3, ss, record(7, b"\x00"), flags=0xC4)):
                self.channel.feed(frame)
        self.connection.send.side_effect = send
        self.assertFalse(self.eq.read(timeout=0.01).success)

    def test_rejection_and_malformed_records(self):
        self.connection.send.side_effect = lambda p: self.channel.feed(response(p[4], p[7], status=3))
        result = self.eq.read()
        self.assertFalse(result.success)
        self.assertIn("0x03", result.message)
        self.connection.send.side_effect = lambda p: self.channel.feed(response(p[4], p[7], b"\xff"))
        self.assertFalse(self.eq.read().success)

    def test_coalesced_wrong_config_then_valid_frame(self):
        def send(packet):
            config = int.from_bytes(packet[8:10], "big")
            data = record(7, b"\x00") if config == 7 else self.custom_data
            self.channel.feed(response(0xF3, packet[7], record(99, b"x")) + response(0xF3, packet[7], data))
        self.connection.send.side_effect = send
        self.assertTrue(self.eq.read().success)

    def test_disconnect_and_old_session_do_not_send(self):
        sent = threading.Event()
        self.connection.send.side_effect = lambda _: sent.set()
        session = self.channel.generation
        results = []
        worker = threading.Thread(target=lambda: results.append(self.eq.read()))
        worker.start()
        self.assertTrue(sent.wait(1))
        self.channel.reset("Disconnected")
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertFalse(results[0].success)
        before = self.connection.send.call_count
        self.assertFalse(self.eq.read(session=session).success)
        self.assertEqual(self.connection.send.call_count, before)

    def test_gesture_and_eq_transactions_share_lock_and_counter(self):
        sent = threading.Event()
        self.connection.send.side_effect = lambda _: sent.set()
        results = []
        first = threading.Thread(target=lambda: results.append(self.eq.read(timeout=1)))
        second = threading.Thread(target=lambda: results.append(self.channel.read(timeout=1)))
        first.start()
        self.assertTrue(sent.wait(1))
        second.start()
        self.assertEqual(self.connection.send.call_count, 1)
        ss = self.channel._pending.counter
        self.connection.send.side_effect = self.send
        self.channel.feed(response(0xF3, ss, record(7, b"\x00")))
        first.join(1)
        second.join(1)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.success for result in results))
        self.assertEqual(len({p[7] for p in self.commands}), len(self.commands))


class EqUITests(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.action = Mock()
        self.panel = EqualizerSettings(self.action, Mock())
        self.state = EqState(0, parse_custom_eq(custom_record()))

    def load(self, state=None):
        self.panel.set_connection(True)
        token = self.panel.begin("read")
        self.panel.complete(token, EqResult(True, state or self.state, m("eq.loaded")), (0, 6, 5, 1, 7), "read")

    def test_connect_and_dynamic_bands(self):
        self.assertTrue(self.panel.refresh_button.disabled)
        self.load()
        self.assertEqual(len(self.panel.sliders), 2)
        self.assertEqual((self.panel.sliders[0].min, self.panel.sliders[0].max), (-10, 10))
        self.assertEqual([o.key for o in self.panel.profile.options], ["0", "6", "5", "1", "7"])
        self.panel.set_connection(False)
        self.assertFalse(self.panel.custom_body.visible)
        self.assertTrue(self.panel.profile.disabled)

    def test_turkish_eq_labels_preserve_unicode(self):
        try:
            set_language("tr")
            self.assertEqual(t("eq.title"), "Ekolayzır")
            self.assertEqual(t("eq.reset"), "Sıfırla")
            self.assertEqual(t("eq.custom"), "Özel EQ")
            self.assertNotIn("?", t("eq.failed", details="timeout"))
        finally:
            set_language("en")

    def test_presets_work_without_custom_eq(self):
        self.load(EqState(0))
        self.assertFalse(self.panel.custom_body.visible)
        self.assertFalse(self.panel.profile.disabled)

    def test_draft_preview_failure_refresh_and_old_token(self):
        self.load()
        slider = self.panel.sliders[0]
        slider.on_change(SimpleNamespace(control=SimpleNamespace(value=4)))
        self.assertEqual(self.panel.draft[0].gain, 4)
        self.assertEqual(self.panel._state.custom.bands[0].gain, -3)
        self.action.assert_not_called()
        slider.on_change_end(None)
        self.assertEqual(self.action.call_args.args, ("preview",))
        token = self.panel.begin("preview")
        self.panel.complete(token, EqResult(True, self.state, m("eq.previewed")), (0, 1, 5, 6, 7), "preview")
        self.assertEqual(self.panel.draft[0].gain, 4)
        self.assertIn("Preview", self.panel.status.value)
        token = self.panel.begin("save")
        self.panel.complete(token, EqResult(False, message=m("eq.timeout")), (), "save")
        self.assertEqual(self.panel.draft[0].gain, 4)
        self.assertTrue(self.panel.save_button.disabled)
        self.assertFalse(self.panel.refresh_button.disabled)
        self.panel.set_connection(False)
        self.panel.set_connection(True)
        self.panel.complete(token, EqResult(True, self.state, "stale"), (), "save")
        self.assertIsNone(self.panel._state)

    def test_pubsub_route(self):
        self.panel.set_connection(True)
        token = self.panel.begin("read")
        page = SimpleNamespace(controls=[], overlay=[], update=Mock())
        handler = AppMessageHandler(page=page, device_status_card=Mock(), settings_card=SimpleNamespace(equalizer=self.panel),
                                    window_manager=Mock(), latency=Mock(), tray=Mock(), debug_console=Mock(),
                                    on_window_show=Mock(), get_game_monitor=Mock())
        handler.handle({"type": "eq_settings", "token": token, "result": EqResult(True, self.state, "loaded"),
                        "profiles": (0, 1), "operation": "read"})
        self.assertEqual(self.panel._state, self.state)
        page.update.assert_called_once()
