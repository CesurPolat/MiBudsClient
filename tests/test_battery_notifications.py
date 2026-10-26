"""Case transitions and battery descriptions use only real, current data."""

import unittest
from unittest.mock import Mock, patch

from ui.app_message_handler import AppMessageHandler
from ui.battery_notifications import BatteryNotificationState
from utils.battery import battery_state
from utils.i18n import LANGUAGES, set_language, t


class BatteryNotificationStateTests(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "en")
        self.state = BatteryNotificationState()
        self.state.reset(active=True)

    def test_only_valid_encoded_battery_levels_are_decoded(self):
        for raw, expected in ((0, (0, False)), (100, (100, False)),
                              (128, (0, True)), (228, (100, True))):
            self.assertEqual(battery_state(raw), expected)
        for raw in (-1, 101, 127, 229, 254, 255, 256, None, True, 60.0, "60"):
            with self.subTest(raw=raw):
                self.assertIsNone(battery_state(raw))

    def test_initial_reading_and_percentage_changes_are_not_removal_events(self):
        self.assertEqual(self.state.update(60, 70, 80), ())
        self.assertEqual(self.state.update(59, 69, 79), ())
        self.assertEqual(self.state.update(188, 198, 80), ())
        self.assertEqual(self.state.update(189, 199, 80), ())

    def test_left_right_and_both_removals_emit_once_per_transition(self):
        self.state.update(188, 198, 80)
        self.assertEqual(self.state.update(60, 198, 80), ("left",))
        self.assertEqual(self.state.update(60, 198, 80), ())
        self.assertEqual(self.state.update(60, 70, 80), ("right",))
        self.state.update(188, 198, 80)
        self.assertEqual(self.state.update(60, 70, 80), ("left", "right"))

    def test_unknown_invalid_and_reconnect_samples_break_the_baseline(self):
        for invalid in (255, 101, 229, None):
            self.state.update(188, 198, 80)
            self.assertEqual(self.state.update(invalid, invalid, 255), ())
            self.assertEqual(self.state.update(60, 70, 80), ())
        self.state.update(188, 198, 80)
        self.state.reset()
        self.assertEqual(self.state.update(60, 70, 80), ())
        self.assertFalse(self.state.has_earbud_data)
        self.state.reset(active=True)
        self.assertEqual(self.state.update(60, 70, 80), ())

    def test_left_right_and_both_insertions_emit_once_per_transition(self):
        self.state.update(188, 198, 80)
        self.assertEqual(self.state.inserted, ())  # first sample is a baseline
        self.state.update(60, 70, 80)
        self.assertEqual(self.state.update(188, 70, 80), ())
        self.assertEqual(self.state.inserted, ("left",))
        self.state.update(188, 70, 80)
        self.assertEqual(self.state.inserted, ())
        self.state.update(188, 198, 80)
        self.assertEqual(self.state.inserted, ("right",))
        self.state.update(60, 70, 80)
        self.state.update(188, 198, 80)
        self.assertEqual(self.state.inserted, ("left", "right"))
        self.state.reset()
        self.assertEqual(self.state.inserted, ())
        self.state.update(188, 198, 80)
        self.assertEqual(self.state.inserted, ())

    def test_insertions_do_not_cross_unknown_invalid_or_reconnect_intervals(self):
        for invalid in (255, 101, 229, None):
            self.state.update(60, 70, 80)
            self.state.update(invalid, invalid, 255)
            self.state.update(188, 198, 80)
            self.assertEqual(self.state.inserted, ())
        self.state.reset(active=True)
        self.state.update(188, 198, 80)
        self.assertEqual(self.state.inserted, ())

    def test_summary_distinguishes_zero_unknown_and_charging_and_is_localized(self):
        self.state.update(0, 228, 255)
        self.assertEqual(self.state.summary(), "LEFT: 0% · RIGHT: ⚡ 100% · CASE: —")
        set_language("tr")
        self.assertEqual(self.state.summary(), "Sol: %0 · Sağ: ⚡ %100 · Kutu: —")
        for language in LANGUAGES:
            set_language(language)
            for event in ("removed_left", "inserted_both"):
                body = self.state.body(t("notification." + event))
                self.assertIn("100", body)
                self.assertIn("—", body)
                self.assertNotIn("notification.", body)


class BatteryNotificationRoutingTests(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "en")
        self.page, self.tray, self.latency = Mock(), Mock(), Mock()
        self.timer_patch = patch("ui.app_message_handler.threading.Timer")
        self.timer = self.timer_patch.start()
        self.addCleanup(self.timer_patch.stop)
        melody_patch = patch("ui.app_message_handler.play_connection_melody")
        melody_patch.start()
        self.addCleanup(melody_patch.stop)
        self.handler = AppMessageHandler(
            page=self.page, tray=self.tray, latency=self.latency,
            device_status_card=Mock(), settings_card=Mock(), window_manager=Mock(),
            debug_console=Mock(), on_window_show=Mock(), get_game_monitor=Mock(),
        )

    def event(self, event):
        self.handler.handle({"type": "connection_event", "event": event})

    def battery(self, left, right, case=255, *, transient=False):
        self.handler.handle({"type": "battery", "left": left, "right": right,
                             "case": case, "transient": transient})

    def timeout(self, token):
        self.handler.handle({"type": "connection_notification_timeout", "token": token})

    def test_connected_notification_waits_for_fresh_battery_then_cancels_timer(self):
        self.event("connected")
        token = self.handler._connection_notification_token
        self.tray.notify.assert_not_called()
        self.timer.assert_called_once()
        self.timer.return_value.start.assert_called_once()
        self.battery(255, 255, transient=True)
        self.battery(255, 255)
        self.tray.notify.assert_not_called()
        self.battery(60, 198, 80)
        self.tray.notify.assert_called_once_with(
            "Earbuds connected\nLEFT: 60% · RIGHT: ⚡ 70% · CASE: 80%", device=True, silent=True)
        self.timer.return_value.cancel.assert_called_once()
        self.timeout(token)
        self.battery(60, 198, 80)
        self.assertEqual(self.tray.notify.call_count, 1)

    def test_timer_only_posts_to_pubsub_and_timeout_sends_one_unknown_summary(self):
        self.event("connected")
        token = self.handler._connection_notification_token
        self.timer.call_args.args[1]()
        self.page.pubsub.send_all.assert_called_once_with({"type": "connection_notification_timeout", "token": token})
        self.tray.notify.assert_not_called()
        self.timeout(token)
        self.tray.notify.assert_called_once_with("Earbuds connected\nLEFT: — · RIGHT: — · CASE: —", device=True, silent=True)
        self.timeout(token)
        self.battery(60, 70)
        self.assertEqual(self.tray.notify.call_count, 1)

    def test_transient_blanking_does_not_hide_a_real_case_removal(self):
        self.event("connected")
        self.battery(188, 198, 80)
        self.tray.reset_mock()
        self.battery(255, 255, transient=True)
        self.tray.notify.assert_not_called()
        self.battery(60, 198, 80)
        self.tray.notify.assert_called_once_with(
            "Left earbud removed from the case\nLEFT: 60% · RIGHT: ⚡ 70% · CASE: 80%", device=True, silent=True)
        self.battery(60, 198, 80)
        self.assertEqual(self.tray.notify.call_count, 1)

    def test_simultaneous_removals_are_combined_and_later_cycles_can_notify(self):
        self.event("connected")
        self.battery(188, 198)
        self.tray.reset_mock()
        self.battery(60, 70)
        self.tray.notify.assert_called_once_with(
            "Both earbuds removed from the case\nLEFT: 60% · RIGHT: 70% · CASE: —", device=True, silent=True)
        self.battery(188, 198)
        self.assertTrue(self.tray.notify.call_args.args[0].startswith("Both earbuds placed"))
        self.battery(188, 70)
        self.assertTrue(self.tray.notify.call_args.args[0].startswith("Right earbud removed"))
        self.assertEqual(self.tray.notify.call_count, 3)

    def test_each_side_inserted_notifies_with_current_charging_battery(self):
        self.event("connected")
        self.battery(60, 70, 80)
        self.tray.reset_mock()
        self.battery(255, 255, transient=True)
        self.battery(188, 70, 80)
        self.tray.notify.assert_called_once_with(
            "Left earbud placed in the case\nLEFT: ⚡ 60% · RIGHT: 70% · CASE: 80%", device=True, silent=True)
        self.battery(188, 70, 80)
        self.assertEqual(self.tray.notify.call_count, 1)
        self.battery(188, 198, 80)
        self.tray.notify.assert_called_with(
            "Right earbud placed in the case\nLEFT: ⚡ 60% · RIGHT: ⚡ 70% · CASE: 80%", device=True, silent=True)
        self.assertEqual(self.tray.notify.call_count, 2)

    def test_both_insertions_are_combined_and_unknown_initial_samples_are_silent(self):
        self.event("connected")
        self.battery(188, 198)
        self.assertEqual(self.tray.notify.call_count, 1)  # connection notice only
        self.battery(255, 255)
        self.battery(188, 198)
        self.assertEqual(self.tray.notify.call_count, 1)
        self.battery(60, 70)
        self.tray.reset_mock()
        self.battery(188, 198)
        self.tray.notify.assert_called_once_with(
            "Both earbuds placed in the case\nLEFT: ⚡ 60% · RIGHT: ⚡ 70% · CASE: —", device=True, silent=True)

    def test_mixed_insertion_and_removal_use_one_notification_with_both_events(self):
        self.event("connected")
        self.battery(188, 70, 80)
        self.tray.reset_mock()
        self.battery(60, 198, 80)
        self.tray.notify.assert_called_once_with(
            "Left earbud removed from the case\nRight earbud placed in the case\n"
            "LEFT: 60% · RIGHT: ⚡ 70% · CASE: 80%", device=True, silent=True)

    def test_disconnect_uses_last_known_data_and_late_samples_cannot_leak_to_reconnect(self):
        self.event("connected")
        self.battery(188, 198, 80)
        self.handler.handle({"type": "connection_state", "state": "failed"})
        self.battery(60, 70, 90)  # late sample from failed connection
        self.event("disconnected")
        self.tray.notify.assert_called_with(
            "Earbuds disconnected\nLast battery data: LEFT: ⚡ 60% · RIGHT: ⚡ 70% · CASE: 80%", device=True, silent=True)
        self.battery(60, 70, 90)
        self.tray.reset_mock()
        self.event("connected")
        self.battery(60, 70)
        self.tray.notify.assert_called_once_with("Earbuds connected\nLEFT: 60% · RIGHT: 70% · CASE: —", device=True, silent=True)

    def test_disconnect_and_close_cancel_pending_connection_notifications(self):
        self.event("connected")
        old_token = self.handler._connection_notification_token
        self.event("disconnected")
        self.timeout(old_token)
        self.assertEqual(self.tray.notify.call_count, 1)
        self.event("connected")
        self.timeout(old_token)
        token = self.handler._connection_notification_token
        self.handler.handle({"type": "app", "action": "close"})
        self.timeout(token)
        self.assertEqual(self.tray.notify.call_count, 1)

    def test_unknown_samples_do_not_generate_false_removals(self):
        self.event("connected")
        self.battery(188, 198)
        self.tray.reset_mock()
        self.battery(255, 101)
        self.battery(60, 70)
        self.tray.notify.assert_not_called()
