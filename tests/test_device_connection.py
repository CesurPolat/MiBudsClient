"""Device callback scheduling and reconnect guard behavior."""

import unittest
from unittest.mock import Mock, call, patch

from controllers.device.controller import DeviceConnection


class DeviceConnectionTests(unittest.TestCase):
    def setUp(self):
        self.publish = Mock()
        self.controller = Mock(connected=False)
        self.connection = DeviceConnection(self.publish, lambda: self.controller)

    def test_status_and_battery_updates_use_publisher(self):
        self.connection.update_status("Connected")
        self.publish.assert_called_once_with({"type": "status", "text": "Connected", "color": "white"})
        with patch.object(self.connection._battery_updates, "update") as update:
            self.connection.update_battery(188, 70, 80)
        update.assert_called_once_with(188, 70, 80)

    def test_battery_request_waits_in_background_then_resumes_connection(self):
        with patch("controllers.device.controller.threading.Thread") as thread, patch(
            "controllers.device.controller.time.sleep",
        ) as sleep:
            self.connection.request_battery_delayed()
            self.controller.request_battery.assert_not_called()
            thread.return_value.start.assert_called_once_with()
            self.assertTrue(thread.call_args.kwargs["daemon"])
            thread.call_args.kwargs["target"]()
        sleep.assert_called_once_with(1)
        self.assertEqual(self.controller.mock_calls, [
            call.resume_reconnect_attempts(), call.request_battery(),
        ])

    def test_show_only_starts_one_reconnect_until_worker_finishes(self):
        with patch("controllers.device.controller.threading.Thread") as thread:
            self.connection.reconnect_on_show()
            self.connection.reconnect_on_show()
            thread.assert_called_once()
            self.assertTrue(thread.call_args.kwargs["daemon"])
            self.controller.reconnect.assert_not_called()
            thread.call_args.kwargs["target"]()
            self.connection.reconnect_on_show()
            self.assertEqual(thread.call_count, 2)
        self.controller.reconnect.assert_called_once_with(force_rediscovery=True)
        self.publish.assert_called_once_with({
            "type": "status", "text": "Connection lost. Reconnecting...", "color": "orange",
        })

    def test_connected_or_uninitialized_device_does_not_reconnect(self):
        with patch("controllers.device.controller.threading.Thread") as thread:
            self.controller.connected = True
            self.connection.reconnect_on_show()
            self.controller = None
            self.connection.reconnect_on_show()
        thread.assert_not_called()

    def test_worker_failure_allows_next_reconnect(self):
        self.controller.reconnect.side_effect = RuntimeError("Disconnected")
        with patch("controllers.device.controller.threading.Thread") as thread:
            self.connection.reconnect_on_show()
            with self.assertRaises(RuntimeError):
                thread.call_args.kwargs["target"]()
            self.connection.reconnect_on_show()
            self.assertEqual(thread.call_count, 2)

    def test_thread_start_failure_allows_next_reconnect(self):
        with patch("controllers.device.controller.threading.Thread") as thread:
            thread.return_value.start.side_effect = RuntimeError("No thread")
            with self.assertRaises(RuntimeError):
                self.connection.reconnect_on_show()
            thread.return_value.start.side_effect = None
            self.connection.reconnect_on_show()
            self.assertEqual(thread.call_count, 2)


if __name__ == "__main__":
    unittest.main()
