"""Behavior checks for latency policy without Bluetooth hardware or a UI."""

import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from threading import Event, Thread
from unittest.mock import Mock, patch

from controllers.latency.controller import LatencyController
from ui.components import SettingsCard


class LatencyControllerTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        defaults = {
            "get_low_latency_mode": "off",
            "get_low_latency_hold_until_app_close": False,
            "get_all_low_latency_exceptions": {"windows": [], "linux": []},
            "get_all_low_latency_includes": {"windows": [], "linux": []},
        }
        for name, value in defaults.items():
            self.stack.enter_context(patch(f"controllers.latency.controller.{name}", return_value=value))
        self.saves = {
            name: self.stack.enter_context(patch(f"controllers.latency.controller.{name}"))
            for name in (
                "set_low_latency_mode", "set_low_latency_hold_until_app_close",
                "set_low_latency_exceptions", "set_low_latency_includes",
            )
        }
        self.stack.enter_context(patch("controllers.latency.controller.threading.Thread"))
        self.device = Mock()
        self.device.send_command.return_value = (True, "OK")
        self.publish = Mock()
        self.rules_changed = Mock()
        self.controller = LatencyController(
            publish=self.publish, get_controller=lambda: self.device,
            get_tray=lambda: None, on_rules_change=self.rules_changed,
            on_ui_update=Mock(),
        )
        self.controller.platform_key = "windows"

    def test_manual_modes_and_invalid_selection(self):
        self.controller.set_selected_latency_mode(" ON ")
        self.device.send_command.assert_called_once_with("low")
        self.controller.set_selected_latency_mode("off")
        self.device.send_command.assert_called_with("std")
        self.controller.set_selected_latency_mode("invalid")
        self.assertEqual(self.device.send_command.call_count, 2)
        self.assertEqual(self.controller.state["selected_mode"], "off")
        self.assertEqual(self.saves["set_low_latency_mode"].call_count, 2)

    def test_auto_fullscreen_exclusion_and_include_precedence(self):
        c = self.controller
        c.set_selected_latency_mode("auto")
        c.on_monitor_state(True, "game.exe")
        self.assertTrue(c.state["effective_low_latency"])
        c.on_monitor_state(False, "game.exe")
        self.assertFalse(c.state["effective_low_latency"])
        c.low_latency_exceptions_by_platform["windows"] = ["game.exe"]
        c.on_monitor_state(True, "game.exe")
        self.assertFalse(c.state["effective_low_latency"])
        c.low_latency_includes_by_platform["windows"] = ["game.exe"]
        c.on_monitor_state(False, "game.exe")
        self.assertTrue(c.state["effective_low_latency"])

    def test_hold_survives_lost_fullscreen_and_ignores_stale_release(self):
        c = self.controller
        c.set_selected_latency_mode("auto")
        c.set_hold_until_app_close_enabled(True)
        with patch.object(c, "is_process_running", return_value=True):
            c.on_monitor_state(True, "game.exe")
            c.on_monitor_state(False, "desktop.exe")
        self.assertTrue(c.state["effective_low_latency"])
        c.on_hold_released("other.exe")
        self.assertTrue(c.state["effective_low_latency"])
        c.on_hold_released("game.exe")
        self.assertFalse(c.state["effective_low_latency"])
        self.assertEqual(c.state["latency_hold_app_id"], "")
        self.device.send_command.assert_called_with("std")

    def test_disabling_hold_reapplies_current_monitor_state(self):
        c = self.controller
        c.set_selected_latency_mode("auto")
        c.set_hold_until_app_close_enabled(True)
        with patch.object(c, "is_process_running", return_value=True):
            c.on_monitor_state(True, "game.exe")
            c.on_monitor_state(False, "desktop.exe")
        c.set_hold_until_app_close_enabled(False)
        self.assertFalse(c.state["effective_low_latency"])
        self.assertEqual(c.state["latency_hold_app_id"], "")

    def test_rules_are_normalized_and_kept_separate_per_platform(self):
        c = self.controller
        c.on_add_low_latency_list_item("windows", " GAME.EXE ")
        c.on_set_low_latency_item_mode("windows", "game.exe", "include")
        self.assertEqual(c.low_latency_exceptions_by_platform["windows"], [])
        self.assertEqual(c.low_latency_includes_by_platform["windows"], ["game.exe"])
        self.assertEqual(c.low_latency_includes_by_platform["linux"], [])
        self.rules_changed.assert_called_with("windows", [], ["game.exe"])
        c.on_remove_low_latency_list_item("windows", "game.exe")
        self.rules_changed.assert_called_with("windows", [], [])
        calls = self.rules_changed.call_count
        c.on_add_low_latency_list_item("invalid", "game.exe")
        self.assertEqual(self.rules_changed.call_count, calls)

    def test_failed_device_command_publishes_error(self):
        self.device.send_command.return_value = (False, "Disconnected")
        self.controller.set_selected_latency_mode("on")
        self.publish.assert_any_call({"type": "status", "text": "Disconnected", "color": "red"})
        self.assertFalse(self.controller.state["effective_low_latency"])
        self.assertEqual(self.controller.get_display_state()["error"], "Disconnected")
        self.device.send_command.return_value = (True, "OK")
        self.controller.set_selected_latency_mode("on")
        self.assertEqual(self.device.send_command.call_count, 2)
        self.assertTrue(self.controller.state["effective_low_latency"])
        self.assertIsNone(self.controller.get_display_state()["error"])

    def test_same_ui_button_retries_failure_but_not_successful_commands(self):
        card = SettingsCard(on_low_latency_mode_change=self.controller.on_latency_mode_change)
        self.device.send_command.return_value = (False, "Disconnected")
        with patch.object(card.latency_item, "update"):
            card.latency_item._mode_buttons["on"].on_click(None)
            self.assertFalse(self.controller.state["effective_low_latency"])
            self.device.send_command.return_value = (True, "OK")
            card.latency_item._mode_buttons["on"].on_click(None)
            self.assertTrue(self.controller.state["effective_low_latency"])
            card.latency_item._mode_buttons["on"].on_click(None)
        self.assertEqual(self.device.send_command.call_count, 2)

    def test_failed_disable_preserves_known_device_state_and_can_retry(self):
        c = self.controller
        c.set_selected_latency_mode("on")
        self.device.send_command.return_value = (False, "Disconnected")
        c.set_selected_latency_mode("off")
        self.assertTrue(c.state["effective_low_latency"])
        self.device.send_command.return_value = (True, "OK")
        c.set_selected_latency_mode("off")
        self.assertFalse(c.state["effective_low_latency"])

    def test_missing_controller_does_not_mark_mode_as_applied(self):
        self.device = None
        self.controller.set_selected_latency_mode("on")
        self.assertFalse(self.controller.state["effective_low_latency"])
        self.assertIsNotNone(self.controller.get_display_state()["error"])

    def test_removing_included_foreground_app_immediately_reapplies_policy(self):
        c = self.controller
        c.set_selected_latency_mode("auto")
        c.on_monitor_state(False, "game.exe")
        c.on_add_low_latency_include_item("windows", "game.exe")
        self.assertTrue(c.state["effective_low_latency"])
        c.on_remove_low_latency_list_item("windows", "game.exe")
        self.assertFalse(c.state["effective_low_latency"])
        self.device.send_command.assert_called_with("std")

    def test_adding_exclusion_immediately_disables_current_fullscreen_app(self):
        c = self.controller
        c.set_selected_latency_mode("auto")
        c.on_monitor_state(True, "game.exe")
        self.assertTrue(c.state["effective_low_latency"])
        c.on_add_low_latency_list_item("windows", "game.exe")
        self.assertFalse(c.state["effective_low_latency"])
        c.on_remove_low_latency_list_item("windows", "game.exe")
        self.assertTrue(c.state["effective_low_latency"])

    def test_other_platform_rules_do_not_reapply_active_platform(self):
        self.controller.set_selected_latency_mode("auto")
        self.device.reset_mock()
        self.controller.on_add_low_latency_include_item("linux", "game")
        self.device.send_command.assert_not_called()

    def test_mode_change_publishes_even_without_a_device_transition(self):
        self.controller.set_selected_latency_mode("auto")
        self.publish.assert_any_call({
            "type": "latency", "enabled": False, "mode": "auto", "source": "manual",
        })

    def test_concurrent_mode_selections_serialize_device_commands(self):
        entered, release, second_started = Event(), Event(), Event()
        errors = []

        def send(mode):
            if mode == "low":
                entered.set()
                if not release.wait(2):
                    raise TimeoutError("Test did not release command")
            return True, "OK"

        def select(mode):
            try:
                if mode == "off":
                    second_started.set()
                self.controller.set_selected_latency_mode(mode)
            except Exception as exc:
                errors.append(exc)

        self.device.send_command.side_effect = send
        first, second = Thread(target=select, args=("on",)), Thread(target=select, args=("off",))
        first.start()
        try:
            self.assertTrue(entered.wait(2))
            second.start()
            self.assertTrue(second_started.wait(2))
            self.assertEqual(self.device.send_command.call_count, 1)
        finally:
            release.set()
            first.join(2)
            if second.ident is not None:
                second.join(2)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual([call.args[0] for call in self.device.send_command.call_args_list], ["low", "std"])
        self.assertEqual(self.controller.get_display_state(), {"mode": "off", "enabled": False, "error": None})

    def test_watcher_publishes_release_and_clears_running_flag(self):
        c = self.controller
        c.state.update(selected_mode="auto", hold_until_app_close_enabled=True,
                       latency_hold_app_id="game.exe")
        with patch("controllers.latency.controller.threading.Thread") as thread, patch.object(
            c, "is_process_running", return_value=False,
        ):
            c.start_hold_watcher_if_needed()
            self.assertTrue(c.state["hold_watcher_running"])
            c.start_hold_watcher_if_needed()
            thread.assert_called_once()
            thread.call_args.kwargs["target"]()
        self.publish.assert_called_with({"type": "auto_hold_released", "app_id": "game.exe"})
        self.assertFalse(c.state["hold_watcher_running"])

    def test_process_discovery_on_windows_and_linux(self):
        for platform, result, expected_command in (
            ("win32", SimpleNamespace(stdout="game.exe 123", returncode=0), "tasklist"),
            ("linux", SimpleNamespace(stdout="123", returncode=0), "pgrep"),
        ):
            with self.subTest(platform=platform), patch("controllers.latency.controller.sys.platform", platform), patch(
                "controllers.latency.controller.subprocess.run", return_value=result,
            ) as run:
                self.assertTrue(self.controller.is_process_running(" GAME.EXE "))
                self.assertEqual(run.call_args.args[0][0], expected_command)


if __name__ == "__main__":
    unittest.main()
