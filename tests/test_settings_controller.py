"""Settings callbacks preserve startup and device identity behavior."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from controllers.settings.controller import SettingsController


class SettingsControllerTests(unittest.TestCase):
    def setUp(self):
        self.device = Mock()
        self.connection = Mock()
        self.publish = Mock()
        self.update = Mock()
        latency = Mock()
        latency.state = {"selected_mode": "auto", "hold_until_app_close_enabled": True}
        latency.platform_key = "windows"
        latency.low_latency_exceptions_by_platform = {"windows": ["excluded.exe"]}
        latency.low_latency_includes_by_platform = {"linux": ["included"]}
        with patch("controllers.settings.controller.is_startup_enabled", return_value=True):
            self.settings = SettingsController(
                controller=self.device, latency=latency, device_connection=self.connection,
                publish=self.publish, on_update=self.update,
            )

    def test_startup_failure_restores_switch_value(self):
        event = SimpleNamespace(control=SimpleNamespace(value=False))
        with patch("controllers.settings.controller.set_startup", return_value=False) as save:
            self.settings.on_startup_change(event)
        save.assert_called_once_with(False)
        self.assertTrue(event.control.value)
        self.connection.update_status.assert_called_once_with("Failed to change startup setting", "red")
        self.update.assert_called_once_with()

    def test_startup_success_keeps_switch_value_and_publishes_status(self):
        event = SimpleNamespace(control=SimpleNamespace(value=False))
        with patch("controllers.settings.controller.set_startup", return_value=True):
            self.settings.on_startup_change(event)
        self.assertFalse(event.control.value)
        self.connection.update_status.assert_called_once_with("Startup disabled", "white")

    def test_identity_query_runs_in_background_and_blocks_duplicate_clicks(self):
        self.device.request_device_identity.return_value = (True, "Redmi Buds 6 Play")
        with patch("controllers.settings.controller.threading.Thread") as thread:
            self.settings.card.identity_item.on_click(None)
            self.settings.card.identity_item.on_click(None)
            self.assertTrue(self.settings.card.identity_item.disabled)
            self.device.request_device_identity.assert_not_called()
            thread.assert_called_once()
            self.assertTrue(thread.call_args.kwargs["daemon"])
            thread.return_value.start.assert_called_once_with()
            thread.call_args.kwargs["target"]()
        self.publish.assert_called_once_with({"type": "device_identity", "text": "Redmi Buds 6 Play"})
        self.connection.update_status.assert_called_once_with("Redmi Buds 6 Play", "green")

    def test_failed_identity_query_still_publishes_completion(self):
        for result, error, expected in (
            ((False, "Disconnected"), None, "Disconnected"),
            (None, RuntimeError("No connection"), "Device identity request failed: No connection"),
        ):
            with self.subTest(error=error), patch("controllers.settings.controller.threading.Thread") as thread:
                self.settings.card.set_device_identity_result("Not queried")
                self.device.request_device_identity.return_value = result
                self.device.request_device_identity.side_effect = error
                self.settings.on_check_device_identity(None)
                thread.call_args.kwargs["target"]()
                self.publish.assert_called_with({"type": "device_identity", "text": expected})
                self.connection.update_status.assert_called_with(expected, "red")

    def test_home_battery_button_and_initial_settings_remain_wired(self):
        card = self.settings.card
        card.home_controls_card.content.controls[-1].on_click(None)
        self.device.request_battery.assert_called_once_with()
        self.assertTrue(card.startup_switch.value)
        self.assertEqual(card.latency_item.value, "auto")
        self.assertEqual(card.content.controls, [card.identity_item])


if __name__ == "__main__":
    unittest.main()
