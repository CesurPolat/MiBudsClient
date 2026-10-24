"""Message handling behavior without a running Flet session."""

import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from ui.app_message_handler import AppMessageHandler
from ui.components.update_notification import show_update_notification
from ui.constants import BATTERY_UNKNOWN, GITHUB_URL


class AppMessageHandlerTests(unittest.TestCase):
    def setUp(self):
        self.page = Mock()
        self.status = Mock()
        self.settings = Mock()
        self.window = Mock()
        self.latency = Mock()
        self.latency.state = {"selected_mode": "off"}
        self.latency.get_display_state.side_effect = lambda: {
            "mode": self.latency.state["selected_mode"],
            "enabled": self.latency.state.get("effective_low_latency", False),
            "error": None,
        }
        self.tray = Mock()
        self.debug = Mock()
        self.reconnect = Mock()
        self.monitor = Mock()
        self.handler = AppMessageHandler(
            page=self.page, device_status_card=self.status,
            settings_card=self.settings, window_manager=self.window,
            latency=self.latency, tray=self.tray, debug_console=self.debug,
            on_window_show=self.reconnect, get_game_monitor=lambda: self.monitor,
        )

    def test_ignores_unrelated_messages(self):
        for message in (None, "hello", {}, {"type": "unknown"}, {"type": []}):
            self.handler.handle(message)
        self.page.update.assert_not_called()
        self.status.update_status.assert_not_called()

    def test_battery_refresh_and_identity_results(self):
        self.handler.handle({"type": "battery", "left": 188, "transient": True})
        self.status.update_battery.assert_called_once_with(
            188, BATTERY_UNKNOWN, BATTERY_UNKNOWN, transient=True,
        )
        self.handler.handle({"type": "device_identity", "text": "Redmi Buds 6 Play"})
        self.settings.set_device_identity_result.assert_called_once_with("Redmi Buds 6 Play")
        self.assertEqual(self.page.update.call_count, 2)

    def test_latency_updates_ui_without_sending_another_command(self):
        self.latency.state.update(selected_mode="auto", effective_low_latency=True)
        self.handler.handle({"type": "latency", "mode": "auto", "enabled": True})
        self.assertEqual(self.latency.state["selected_mode"], "auto")
        self.assertTrue(self.latency.state["effective_low_latency"])
        self.settings.set_latency_mode.assert_called_once_with("auto")
        self.page.pubsub.send_all.assert_called_once_with(
            {"type": "status", "text": "Automatic mode set", "color": "blue"},
        )
        self.latency.set_selected_latency_mode.assert_not_called()

    def test_late_latency_message_cannot_restore_old_state(self):
        self.latency.state.update(selected_mode="on", effective_low_latency=True)
        self.handler.handle({"type": "latency", "mode": "off", "enabled": False})
        self.assertEqual(self.latency.state["selected_mode"], "on")
        self.assertTrue(self.latency.state["effective_low_latency"])
        self.settings.set_latency_mode.assert_called_once_with("on")

    def test_failed_command_does_not_display_a_success_status(self):
        self.latency.get_display_state.side_effect = None
        self.latency.get_display_state.return_value = {
            "mode": "on", "enabled": False, "error": "Disconnected",
        }
        self.handler.handle({"type": "latency", "mode": "off", "enabled": False})
        self.page.pubsub.send_all.assert_called_once_with(
            {"type": "status", "text": "Disconnected", "color": "red"},
        )

    def test_connection_notifications_are_deduplicated(self):
        for event in ("connected", "connected", "disconnected", "disconnected"):
            self.handler.handle({"type": "connection_event", "event": event})
        self.assertEqual(self.tray.notify.call_args_list, [
            call("Earbuds connected"), call("Earbuds disconnected"),
        ])
        self.latency.clear_latency_hold.assert_called_once_with()

    def test_window_and_monitor_messages(self):
        self.handler.handle({"type": "window", "action": "show"})
        self.window.apply_show.assert_called_once_with()
        self.reconnect.assert_called_once_with()
        self.handler.handle({"type": "window", "action": "hide"})
        self.window.apply_hide.assert_called_once_with()
        self.handler.handle({"type": "fullscreen_state", "is_fullscreen": True, "app_id": " GAME.EXE "})
        self.latency.on_monitor_state.assert_called_once_with(True, "game.exe")
        self.handler.handle({"type": "auto_hold_released", "app_id": "game.exe"})
        self.latency.on_hold_released.assert_called_once_with("game.exe")

    def test_debug_toggle_is_debounced(self):
        self.debug.toggle_console.return_value = "opened"
        with patch("ui.app_message_handler.time.monotonic", side_effect=[10, 10.1, 10.5]):
            for _ in range(3):
                self.handler.handle({"type": "debug_console", "action": "toggle"})
        self.assertEqual(self.debug.toggle_console.call_count, 2)
        self.status.update_status.assert_called_with("Debug console opened", "blue")

    def test_close_stops_monitor_and_hotkey_before_closing_window(self):
        order = Mock()
        order.attach_mock(self.monitor.stop, "monitor")
        order.attach_mock(self.debug.stop_f12_hotkey_listener, "hotkey")
        order.attach_mock(self.window.close, "close")
        self.handler.handle({"type": "app", "action": "other"})
        self.assertEqual(order.mock_calls, [])
        self.handler.handle({"type": "app", "action": "close"})
        self.assertEqual(order.mock_calls, [call.monitor(), call.hotkey(), call.close()])

    def test_update_notification_actions(self):
        self.page.overlay = []
        show_update_notification(self.page, "")
        self.assertEqual(self.page.overlay, [])
        show_update_notification(self.page, "v1.2.3")
        snack = self.page.overlay[0]
        self.assertTrue(snack.open)
        checkbox = snack.content.controls[1].controls[0]
        download = snack.content.controls[2]
        with patch("ui.components.update_notification.suppress_update_notification") as suppress:
            checkbox.on_change(SimpleNamespace(control=SimpleNamespace(value=True)))
            suppress.assert_called_once_with("v1.2.3")
        with patch("ui.components.update_notification.webbrowser.open") as open_url:
            download.on_click(None)
            open_url.assert_called_once_with(GITHUB_URL)
        self.assertFalse(snack.open)

    def test_startup_mounts_home_controls_before_subscribing(self):
        import main

        with ExitStack() as stack:
            for name in ("WindowManager", "SystemTray", "DebugConsoleManager",
                         "BTController", "FullscreenGameMonitor", "start_instance_listener",
                         "start_update_check", "CatalogSync"):
                stack.enter_context(patch.object(main, name))
            stack.enter_context(patch.object(main.threading, "Thread"))
            main.CatalogSync.return_value.cached_device = ('Saved earbuds', 'assets/images/MiBuds6Play.png')
            stack.enter_context(patch("controllers.settings.controller.is_startup_enabled", return_value=False))
            latency = stack.enter_context(patch.object(main, "LatencyController")).return_value
            latency.state = {"selected_mode": "off", "hold_until_app_close_enabled": False}
            latency.platform_key = "windows"
            latency.low_latency_exceptions_by_platform = {}
            latency.low_latency_includes_by_platform = {}
            main.main(self.page)

        handler = self.page.pubsub.subscribe.call_args.args[0].__self__
        layout = self.page.add.call_args.args[0]
        home, settings = layout.page_content.controls
        self.assertEqual(home.content.controls, [
            handler._device_status_card, handler._settings_card.home_controls_card,
        ])
        self.assertIs(settings.content, handler._settings_card)
        self.assertEqual(handler._device_status_card.device_name.value, 'Saved earbuds')
        self.assertTrue(handler._device_status_card.device_image._image_control.src.endswith('MiBuds6Play.png'))
        self.assertIs(settings.content.content.controls[0], handler._settings_card.startup_item)
        self.assertIs(settings.content.content.controls[-1], handler._settings_card.identity_item)
        calls = [c[0] for c in self.page.mock_calls]
        self.assertLess(calls.index("add"), calls.index("pubsub.subscribe"))


if __name__ == "__main__":
    unittest.main()
