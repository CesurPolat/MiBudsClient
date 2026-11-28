"""Message handling behavior without a running Flet session."""

import asyncio
import inspect
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from pubsub_fakes import subscribe_test_ui
from ui.app_subscriptions import subscribe_ui_topic
from ui.components.dialogs.update_notification import show_update_notification
from controllers.battery.stream import BATTERY_UNKNOWN
from ui.constants import GITHUB_URL
from utils.app.pubsub_topics import PubSubTopic


class AppSubscriptionTests(unittest.TestCase):
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
        self.timer_patch = patch("ui.battery_notifications.threading.Timer")
        self.timer_patch.start()
        self.addCleanup(self.timer_patch.stop)
        self.melody_patch = patch("ui.battery_notifications.play_connection_melody")
        self.melody = self.melody_patch.start()
        self.addCleanup(self.melody_patch.stop)
        self.disconnect_melody_patch = patch("ui.battery_notifications.play_disconnection_melody")
        self.disconnect_melody = self.disconnect_melody_patch.start()
        self.addCleanup(self.disconnect_melody_patch.stop)
        self.identity = None
        self.deliver = subscribe_test_ui(
            page=self.page, device_status_card=self.status,
            settings_card=self.settings, window_manager=self.window,
            latency=self.latency, tray=self.tray, debug_console=self.debug,
            on_window_show=self.reconnect, get_identity=lambda: self.identity,
        )

    def test_ignores_unrelated_messages(self):
        callback = dict(item.args for item in self.page.pubsub.subscribe_topic.call_args_list)["status"]
        for message in (None, "hello", []):
            asyncio.run(callback("status", message))
        self.deliver("unknown")
        self.page.update.assert_not_called()
        self.status.update_status.assert_not_called()

    def test_disconnect_sound_requires_a_connection_and_is_deduplicated(self):
        self.deliver("connection_event", event="disconnected")
        self.disconnect_melody.assert_not_called()
        for event in ("connected", "disconnected", "disconnected"):
            self.deliver("connection_event", event=event)
        self.disconnect_melody.assert_called_once_with()
        self.deliver("app", action="close")
        self.deliver("connection_event", event="disconnected")
        self.disconnect_melody.assert_called_once_with()

    def test_battery_refresh_and_identity_results(self):
        self.deliver("battery", left=188, transient=True)
        self.status.update_battery.assert_called_once_with(
            188, BATTERY_UNKNOWN, BATTERY_UNKNOWN, transient=True,
        )
        self.deliver("device_identity", text="Redmi Buds 6 Play")
        self.settings.set_device_identity_result.assert_called_once_with("Redmi Buds 6 Play")
        self.assertEqual(self.page.update.call_count, 2)

    def test_firmware_update_rejects_stale_session(self):
        identity = SimpleNamespace(firmware_version="2.0.2.2")
        self.identity = identity
        self.deliver("firmware_info", identity=identity)
        self.settings.set_firmware_version.assert_called_once_with("2.0.2.2")
        self.identity = None
        self.deliver("firmware_info", identity=identity)
        self.settings.set_firmware_version.assert_called_once()

    def test_latency_updates_ui_without_sending_another_command(self):
        self.latency.state.update(selected_mode="auto", effective_low_latency=True)
        self.deliver("latency", mode="auto", enabled=True)
        self.assertEqual(self.latency.state["selected_mode"], "auto")
        self.assertTrue(self.latency.state["effective_low_latency"])
        self.settings.set_latency_mode.assert_called_once_with("auto")
        self.page.pubsub.send_all_on_topic.assert_called_once_with(
            "status", {"text": "Game Mode set", "color": "blue"},
        )
        self.latency.set_selected_latency_mode.assert_not_called()

    def test_late_latency_message_cannot_restore_old_state(self):
        self.latency.state.update(selected_mode="on", effective_low_latency=True)
        self.deliver("latency", mode="off", enabled=False)
        self.assertEqual(self.latency.state["selected_mode"], "on")
        self.assertTrue(self.latency.state["effective_low_latency"])
        self.settings.set_latency_mode.assert_called_once_with("on")

    def test_failed_command_does_not_display_a_success_status(self):
        self.latency.get_display_state.side_effect = None
        self.latency.get_display_state.return_value = {
            "mode": "on", "enabled": False, "error": "Disconnected",
        }
        self.deliver("latency", mode="off", enabled=False)
        self.page.pubsub.send_all_on_topic.assert_called_once_with(
            "status", {"text": "Disconnected", "color": "red"},
        )

    def test_connection_notifications_are_deduplicated(self):
        for event in ("connected", "connected"):
            self.deliver("connection_event", event=event)
        self.tray.notify.assert_not_called()
        self.deliver("battery", left=60, right=70, case=255)
        for event in ("disconnected", "disconnected"):
            self.deliver("connection_event", event=event)
        self.assertEqual(self.tray.notify.call_args_list, [
            call("Earbuds connected\nLEFT: 60% · RIGHT: 70% · CASE: —", device=True, silent=True),
            call("Earbuds disconnected\nLast battery data: LEFT: 60% · RIGHT: 70% · CASE: —", device=True, silent=True),
        ])
        self.latency.clear_latency_hold.assert_called_once_with()

    def test_first_successful_connection_plays_melody_once_per_app_session(self):
        self.deliver("connection_state", state="connecting")
        self.deliver("connection_state", state="failed")
        self.deliver("connection_event", event="reconnect_failed_limit")
        self.melody.assert_not_called()
        self.deliver("connection_event", event="connected")
        self.melody.assert_called_once_with()
        self.tray.notify.assert_not_called()  # audio does not wait for the battery description
        for event in ("connected", "disconnected", "connected", "connected"):
            self.deliver("connection_event", event=event)
        self.deliver("battery", left=60, right=70, case=255)
        self.melody.assert_called_once_with()
        for item in self.tray.notify.call_args_list:
            self.assertTrue(item.kwargs["silent"])

    def test_catalog_image_is_shared_with_screen_and_tray(self):
        self.deliver("catalog_device", name="Redmi Buds 6 Play", image_path="cached.png")
        self.status.update_catalog_device.assert_called_once_with("Redmi Buds 6 Play", "cached.png")
        self.tray.set_device.assert_called_once_with("Redmi Buds 6 Play", "cached.png")

    def test_window_and_monitor_messages(self):
        self.deliver("window", action="show")
        self.window.apply_show.assert_called_once_with()
        self.reconnect.assert_called_once_with()
        self.deliver("window", action="hide")
        self.window.apply_hide.assert_called_once_with()
        self.deliver("fullscreen_state", is_fullscreen=True, app_id=" GAME.EXE ")
        self.latency.on_monitor_state.assert_called_once_with(True, "game.exe")
        self.deliver("auto_hold_released", app_id="game.exe")
        self.latency.on_hold_released.assert_called_once_with("game.exe")

    def test_debug_toggle_is_debounced(self):
        self.debug.toggle_console.return_value = "opened"
        with patch("ui.app_events.time.monotonic", side_effect=[10, 10.1, 10.5]):
            for _ in range(3):
                self.deliver("debug_console", action="toggle")
        self.assertEqual(self.debug.toggle_console.call_count, 2)
        self.status.update_status.assert_called_with("Debug console opened", "blue")

    def test_close_delegates_to_window_manager(self):
        order = Mock()
        order.attach_mock(self.debug.stop_f12_hotkey_listener, "hotkey")
        order.attach_mock(self.window.close, "close")
        self.deliver("app", action="other")
        self.assertEqual(order.mock_calls, [])
        self.deliver("app", action="close")
        self.assertEqual(order.mock_calls, [call.close()])

    def test_late_messages_after_close_do_not_update_detached_controls(self):
        self.deliver('app', action='close')
        self.page.update.reset_mock()
        self.deliver('latency')
        self.deliver('battery', left=50, right=50, case=50)
        self.deliver('app', action='close')
        self.settings.set_latency_mode.assert_not_called()
        self.page.update.assert_not_called()
        self.window.close.assert_called_once()

    def test_update_notification_actions(self):
        self.page.overlay = []
        show_update_notification(self.page, "")
        self.assertEqual(self.page.overlay, [])
        show_update_notification(self.page, "v1.2.3")
        snack = self.page.overlay[0]
        self.assertTrue(snack.open)
        checkbox = snack.content.controls[1].controls[0]
        download = snack.content.controls[2]
        with patch("ui.components.dialogs.update_notification.suppress_update_notification") as suppress:
            checkbox.on_change(SimpleNamespace(control=SimpleNamespace(value=True)))
            suppress.assert_called_once_with("v1.2.3")
        with patch("ui.components.dialogs.update_notification.webbrowser.open") as open_url:
            download.on_click(None)
            open_url.assert_called_once_with(GITHUB_URL + "/releases/latest")
        self.assertFalse(snack.open)

    def test_startup_mounts_home_controls_before_subscribing(self):
        import main

        self.page.reset_mock()
        with ExitStack() as stack:
            for name in ("WindowManager", "SystemTray", "DebugConsoleManager",
                         "BTController", "FullscreenGameMonitor", "start_instance_listener",
                         "start_update_check", "CatalogSync", "ReportQueue", "ErrorReportManager",
                         "ErrorReportDialog"):
                stack.enter_context(patch.object(main, name))
            stack.enter_context(patch.object(main, "threading", SimpleNamespace(
                Thread=Mock(), RLock=threading.RLock)))
            main.CatalogSync.return_value.cached_device = ('Saved earbuds', 'assets/images/MiBuds6Play.png')
            stack.enter_context(patch("controllers.settings.controller.reconcile_startup", return_value=False))
            latency = stack.enter_context(patch.object(main, "LatencyController")).return_value
            latency.state = {"selected_mode": "off", "hold_until_app_close_enabled": False}
            latency.platform_key = "windows"
            latency.low_latency_exceptions_by_platform = {}
            latency.low_latency_includes_by_platform = {}
            setup = stack.enter_context(patch.object(
                main, "subscribe_ui_events", wraps=main.subscribe_ui_events,
            ))
            asyncio.run(main.main(self.page))
            main.WindowManager.assert_called_once_with(
                self.page, auto_resize=True, on_shutdown=main.application_shutdown.stop)

        subscriber = self.page.pubsub.subscribe_topic.call_args.args[1]
        self.assertTrue(inspect.iscoroutinefunction(subscriber))
        status_card = setup.call_args.kwargs["device_status_card"]
        settings_card = setup.call_args.kwargs["settings_card"]
        tray = setup.call_args.kwargs["tray"]
        layout = self.page.add.call_args.args[0].content
        home, settings = layout.page_content.controls
        self.assertIs(home.content.controls[0].controls[0].content, status_card)
        self.assertIs(home.content.controls[1], settings_card.home_controls_card)
        self.assertIs(settings.content, settings_card)
        self.assertEqual(status_card.device_name.value, 'Saved earbuds')
        self.assertTrue(status_card.device_image._image_control.src.endswith('MiBuds6Play.png'))
        tray.set_device.assert_called_once_with('Saved earbuds', 'assets/images/MiBuds6Play.png')
        self.assertIs(settings.content._sections["general"].content.controls[0], settings_card.startup_item)
        self.assertIs(settings.content._sections["identity"], settings_card.identity_section)
        calls = [c[0] for c in self.page.mock_calls]
        self.assertLess(calls.index("add"), calls.index("pubsub.subscribe_topic"))


class PubSubUiLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_messages_and_native_updates_share_ui_thread(self):
        from flet.pubsub.pubsub_client import PubSubClient
        from flet.pubsub.pubsub_hub import PubSubHub

        loop = asyncio.get_running_loop()
        ui_thread = threading.get_ident()
        observed = []
        finished = asyncio.Event()

        def apply(message):
            observed.append((message['index'], threading.get_ident()))
            # Model a native Flet update scheduled while applying a message.
            loop.call_soon(native_update, message['index'])
            observed.append(('committed', threading.get_ident()))
            if message['index'] == 99:
                finished.set()

        native = []

        def native_update(index):
            # The entire mutation/update pair must have completed first.
            self.assertIn((index, ui_thread), observed)
            self.assertEqual(len(observed) % 2, 0)
            native.append(threading.get_ident())

        with ThreadPoolExecutor(max_workers=4) as executor:
            hub = PubSubHub(loop=loop, executor=executor)
            pubsub = PubSubClient(hub, 'test')
            subscribe_ui_topic(
                pubsub, PubSubTopic.STATUS, apply, ui_lock=threading.RLock(), is_closing=lambda: False,
            )

            def produce():
                for index in range(100):
                    pubsub.send_all_on_topic(PubSubTopic.STATUS.value, {'index': index})

            await asyncio.to_thread(produce)
            await asyncio.wait_for(finished.wait(), timeout=3)
            await asyncio.sleep(0)

        self.assertEqual([index for index, _ in observed[::2]], list(range(100)))
        self.assertTrue(all(thread == ui_thread for _, thread in observed))
        self.assertEqual(native, [ui_thread] * 100)


if __name__ == "__main__":
    unittest.main()
