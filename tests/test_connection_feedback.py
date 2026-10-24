"""Connection feedback must survive unrelated UI updates and recover on retry."""

import unittest
from unittest.mock import Mock, patch

from controllers.bluetooth.controller import BTController
from ui.components.device_status import DeviceStatusCard
from ui.components.connection import ConnectionPanel
from ui.components.settings_card import SettingsCard


class ConnectionFeedbackTests(unittest.TestCase):
    def test_controls_only_appear_after_connection_and_survive_reconnect(self):
        card = SettingsCard(low_latency_mode="auto")
        self.assertTrue(card.connection_panel.visible)
        self.assertTrue(card.connection_panel.connection_progress.visible)
        self.assertFalse(card.connected_controls.visible)
        card.update_connection_state("connected")
        self.assertFalse(card.connection_panel.visible)
        self.assertTrue(card.connected_controls.visible)
        card.update_connection_state("failed", "Connection lost")
        self.assertFalse(card.connected_controls.visible)
        self.assertTrue(card.connection_panel.visible)
        self.assertTrue(card.connection_panel.retry_button.visible)
        card.update_connection_state("connecting")
        self.assertFalse(card.connected_controls.visible)
        self.assertTrue(card.connection_panel.connection_progress.visible)
        card.update_connection_state("connected")
        self.assertTrue(card.connected_controls.visible)
        self.assertEqual(card.latency_item.value, "auto")

    def make_controller(self):
        feedback = Mock()
        controller = BTController(connection_state_callback=feedback)
        controller._connection = Mock(connected=False)
        controller.on_connect_setup = Mock()
        return controller, feedback

    def test_missing_device_reports_actionable_failure_after_connecting(self):
        controller, feedback = self.make_controller()
        with patch("controllers.bluetooth.controller.BluetoothDiscovery.get_connected_device", return_value=None):
            self.assertFalse(controller.connect())
        self.assertEqual(feedback.call_args_list[0].args, ("connecting", ""))
        state, reason = feedback.call_args.args
        self.assertEqual(state, "failed")
        self.assertIn("No connected earbuds found in the catalog", reason)
        controller._connection.connect.assert_not_called()

    def test_socket_timeout_keeps_reason_and_success_clears_it(self):
        controller, feedback = self.make_controller()
        controller._bd_addr = "AA:BB:CC:DD:EE:FF"
        controller._connection.connect.side_effect = TimeoutError("timed out")
        self.assertFalse(controller.connect())
        self.assertEqual(feedback.call_args.args[0], "failed")
        self.assertIn("connection timed out", feedback.call_args.args[1])
        self.assertIn("timed out", feedback.call_args.args[1])
        controller._connection.connect.side_effect = None
        self.assertTrue(controller.connect())
        feedback.assert_called_with("connected", "")

    def test_discovery_exception_reports_failure(self):
        controller, feedback = self.make_controller()
        with patch("controllers.bluetooth.controller.BluetoothDiscovery.get_connected_device", side_effect=PermissionError("denied")):
            self.assertFalse(controller.connect())
        self.assertIn("access was denied", feedback.call_args.args[1])

    def test_queued_retry_does_not_disconnect_new_connection(self):
        controller, feedback = self.make_controller()
        controller._connection.connected = True
        self.assertTrue(controller.reconnect(force_rediscovery=True))
        controller._connection.disconnect.assert_not_called()

    def test_failure_survives_status_and_battery_then_retry_resets_controls(self):
        card = ConnectionPanel()
        summary = DeviceStatusCard()
        card.update_connection_state("failed", "Test failure")
        summary.update_status("Other status")
        summary.update_battery(60, 70, 80)
        self.assertEqual(card.connection_reason.value, "Test failure")
        self.assertTrue(card.retry_button.visible)
        card.update_connection_state("connecting")
        self.assertTrue(card.connection_progress.visible)
        self.assertFalse(card.retry_button.visible)
        self.assertFalse(card.connection_reason.visible)
        card.update_connection_state("connected")
        self.assertFalse(card.connection_progress.visible)
        self.assertFalse(card.retry_button.visible)
        self.assertEqual(card.connection_reason.value, "")


if __name__ == "__main__":
    unittest.main()
