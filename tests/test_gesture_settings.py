"""Flet states and background gesture completion routing without hardware."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from controllers.bluetooth.gestures import GestureResult, gesture_capabilities
from controllers.settings.gestures import GestureSettingsController
from ui.components.gestures import GestureSettings
from ui.components.settings_card import SettingsCard
from ui.app_message_handler import AppMessageHandler


class GestureSettingsTests(unittest.TestCase):
    def setUp(self):
        self.refresh = Mock()
        self.assign = Mock()
        self.panel = GestureSettings(self.refresh, self.assign, Mock())
        self.panel.set_connection(True)

    def load(self, assignments=None, capabilities=None):
        token = self.panel.begin("Reading")
        self.panel.complete(token, GestureResult(True, assignments or {1: (1, 3)}, "Loaded"),
                            capabilities or {1: (1, 3, 8)})

    def test_open_and_reopen_refresh_but_disconnected_open_does_not(self):
        self.panel._toggle(None)
        self.assertTrue(self.panel.body.visible)
        self.refresh.assert_called_once()
        self.panel._toggle(None)
        self.panel._toggle(None)
        self.assertEqual(self.refresh.call_count, 2)
        self.panel.set_connection(False)
        self.panel._toggle(None)
        self.panel._toggle(None)
        self.assertEqual(self.refresh.call_count, 2)
        self.panel.set_connection(True)
        self.assertEqual(self.refresh.call_count, 3)

    def test_only_intersection_of_returned_gestures_and_capabilities_is_editable(self):
        self.load({1: (1, 3), 2: (2, 3), 4: (1, 1)}, {1: (1, 3), 3: (0, 8)})
        self.assertEqual(set(self.panel.selectors), {(1, "left"), (1, "right")})
        self.assertEqual([option.key for option in self.panel.selectors[(1, "left")].options], ["1", "3"])

    def test_unknown_current_action_is_preserved_and_not_offered_as_a_new_assignment(self):
        self.load({1: (254, 3)})
        selector = self.panel.selectors[(1, "left")]
        self.assertEqual(selector.value, "254")
        self.assertIn("0xFE", selector.options[-1].text)
        self.assertTrue(selector.options[-1].disabled)
        selector.on_select(SimpleNamespace(control=SimpleNamespace(value="254")))
        self.assign.assert_not_called()

    def test_single_tap_uses_model_options_and_targets_each_side(self):
        self.load({4: (8, 8)}, gesture_capabilities("Redmi Buds 6 Play"))
        for side in ("left", "right"):
            selector = self.panel.selectors[(4, side)]
            self.assertEqual(selector.value, "8")
            self.assertEqual([option.key for option in selector.options], ["8", "1", "4", "5", "2", "3", "9"])
            selector.on_select(SimpleNamespace(control=SimpleNamespace(value="1")))
            self.assign.assert_called_with(4, side, 1)

    def test_single_tap_title_is_localized_in_all_languages(self):
        from utils.i18n import render
        from ui.components.gestures import GESTURE_NAMES
        for language, expected in (("en", "Single tap"), ("tr", "Tek dokunuş"), ("zh-CN", "单击")):
            self.assertEqual(render(GESTURE_NAMES[4], language), expected)

    def test_changes_target_one_side_and_noop_does_not_write(self):
        self.load()
        selector = self.panel.selectors[(1, "left")]
        selector.on_select(SimpleNamespace(control=SimpleNamespace(value="1")))
        self.assign.assert_not_called()
        selector.on_select(SimpleNamespace(control=SimpleNamespace(value="8")))
        self.assign.assert_called_once_with(1, "left", 8)
        self.assertEqual(self.panel.selectors[(1, "right")].value, "3")

    def test_busy_state_blocks_refresh_and_duplicate_operations(self):
        self.load()
        token = self.panel.begin("Saving")
        self.assertIsNotNone(token)
        self.assertIsNone(self.panel.begin("Again"))
        self.panel._refresh()
        self.refresh.assert_not_called()
        self.assertTrue(self.panel.refresh_button.disabled)
        self.assertTrue(all(selector.disabled for selector in self.panel.selectors.values()))

    def test_failure_keeps_verified_values_until_explicit_refresh(self):
        self.load()
        token = self.panel.begin("Saving")
        self.panel.complete(token, GestureResult(False, message="Not verified"), {})
        self.assertEqual(self.panel.selectors[(1, "left")].value, "1")
        self.assertEqual(self.panel.status.value, "Not verified")
        self.assertTrue(self.panel.selectors[(1, "left")].disabled)
        self.assertFalse(self.panel.refresh_button.disabled)
        self.load()
        self.assertFalse(self.panel.selectors[(1, "left")].disabled)

    def test_disconnect_clears_and_discards_old_completions_after_reconnect(self):
        self.load()
        token = self.panel.begin("Saving")
        self.panel.set_connection(False)
        self.assertEqual(self.panel.selectors, {})
        self.panel.set_connection(True)
        self.panel.complete(token, GestureResult(True, {1: (8, 3)}, "Old result"), {1: (1, 8)})
        self.assertEqual(self.panel.selectors, {})
        self.assertNotEqual(self.panel.status.value, "Old result")

    def test_duplicate_completion_cannot_overwrite_newer_refresh(self):
        token = self.panel.begin("Reading")
        self.panel.complete(token, GestureResult(True, {1: (1, 3)}, "First"), {1: (1, 3)})
        newer = self.panel.begin("Refresh")
        self.panel.complete(token, GestureResult(True, {1: (8, 3)}, "Old"), {1: (1, 8)})
        self.assertEqual(self.panel.status.value, "Refresh")
        self.panel.complete(newer, GestureResult(True, {1: (3, 3)}, "New"), {1: (1, 3)})
        self.assertEqual(self.panel.selectors[(1, "left")].value, "3")

    def test_card_connection_state_reaches_gesture_panel(self):
        card = SettingsCard()
        card.update_connection_state("connected")
        self.assertFalse(card.gestures.refresh_button.disabled)
        card.update_connection_state("failed")
        self.assertTrue(card.gestures.refresh_button.disabled)

    def test_background_request_publishes_completion_without_updating_controls(self):
        device, publish = Mock(), Mock()
        device.gesture_session = 7
        device.gesture_capabilities = {1: (1, 3)}
        device.request_gesture_settings.return_value = GestureResult(True, {1: (1, 3)}, "Loaded")
        worker = GestureSettingsController(device, self.panel, publish)
        with patch("controllers.settings.gestures.threading.Thread") as thread:
            worker.refresh()
            worker.refresh()
            thread.assert_called_once()
            self.assertTrue(thread.call_args.kwargs["daemon"])
            device.request_gesture_settings.assert_not_called()
            thread.call_args.kwargs["target"]()
        device.request_gesture_settings.assert_called_once_with(session=7)
        self.assertEqual(self.panel.selectors, {})
        message = publish.call_args.args[0]
        self.panel.complete(message["token"], message["result"], message["capabilities"])
        self.assertEqual(self.panel.selectors[(1, "left")].value, "1")

    def test_background_exception_still_releases_busy_state_via_completion(self):
        device, publish = Mock(), Mock()
        device.request_gesture_settings.side_effect = RuntimeError("Failed")
        worker = GestureSettingsController(device, self.panel, publish)
        with patch("controllers.settings.gestures.threading.Thread") as thread:
            worker.refresh()
            thread.call_args.kwargs["target"]()
        message = publish.call_args.args[0]
        self.panel.complete(message["token"], message["result"], message["capabilities"])
        self.assertIn("Failed", self.panel.status.value)
        self.assertFalse(self.panel.refresh_button.disabled)

    def test_message_handler_routes_result_to_panel(self):
        card, page = Mock(), Mock()
        handler = AppMessageHandler(page=page, device_status_card=Mock(), settings_card=card,
                                    window_manager=Mock(), latency=Mock(), tray=Mock(), debug_console=Mock(),
                                    on_window_show=Mock(), get_game_monitor=Mock())
        result = GestureResult(True, {1: (1, 3)}, "Loaded")
        handler.handle({"type": "gesture_settings", "token": 4, "result": result, "capabilities": {1: (1, 3)}})
        card.gestures.complete.assert_called_once_with(4, result, {1: (1, 3)})
        page.update.assert_called_once()


if __name__ == "__main__":
    unittest.main()
