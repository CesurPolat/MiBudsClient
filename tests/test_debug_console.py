"""Debug keyboard input publishes messages without opening a native console."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from utils.debug_console import DebugConsoleManager


class DebugKeyboardTests(unittest.TestCase):
    def test_f12_publishes_toggle_on_windows(self):
        publish = Mock()
        manager = DebugConsoleManager(publish=publish)
        with patch("utils.debug_console.sys.platform", "win32"), patch.object(
            manager, "toggle_console",
        ) as toggle:
            manager.handle_keyboard_event(SimpleNamespace(key="f12"))
        publish.assert_called_once_with({"type": "debug_console", "action": "toggle"})
        toggle.assert_not_called()

    def test_f12_publishes_toggle_on_linux(self):
        publish = Mock()
        manager = DebugConsoleManager(publish=publish)
        with patch("utils.debug_console.sys.platform", "linux"):
            manager.handle_keyboard_event(SimpleNamespace(key="F12"))
        publish.assert_called_once_with({"type": "debug_console", "action": "toggle"})

    def test_linux_toggle_uses_bound_flet_console(self):
        manager = DebugConsoleManager()
        toggle = Mock(side_effect=["opened", "closed"])
        manager.set_ui_console(toggle)
        with patch("utils.debug_console.os.name", "posix"):
            self.assertEqual(manager.toggle_console(), "opened")
            self.assertEqual(manager.toggle_console(), "closed")
        self.assertEqual(toggle.call_count, 2)

    def test_windows_retains_native_console(self):
        manager = DebugConsoleManager()
        ui = Mock()
        manager.set_ui_console(ui)
        def opened():
            manager._console_visible = True
        with patch("utils.debug_console.os.name", "nt"), patch.object(
            manager, "_open_windows_console", side_effect=opened,
        ) as open_console, patch.object(manager, "_close_windows_console") as close_console:
            self.assertEqual(manager.toggle_console(), "opened")
            self.assertEqual(manager.toggle_console(), "closed")
        open_console.assert_called_once()
        close_console.assert_called_once()
        ui.assert_not_called()

    def test_clear_discards_captured_logs(self):
        manager = DebugConsoleManager()
        manager._append_log("out\n", "stdout")
        manager._append_log("failure\n", "stderr")
        self.assertEqual(manager.get_recent_logs(), "out\n[ERR] failure\n")
        manager.clear_logs()
        self.assertEqual(manager.get_recent_logs(), "")

    def test_other_keys_and_missing_key_are_ignored(self):
        publish = Mock()
        manager = DebugConsoleManager(publish=publish)
        for event in (SimpleNamespace(key="F11"), SimpleNamespace(), None):
            manager.handle_keyboard_event(event)
        publish.assert_not_called()

    def test_existing_constructor_does_not_require_publisher(self):
        manager = DebugConsoleManager(100)
        manager.handle_keyboard_event(SimpleNamespace(key="F12"))
        self.assertEqual(manager.get_recent_logs(), "")


if __name__ == "__main__":
    unittest.main()
