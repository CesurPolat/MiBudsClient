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

    def test_f12_reports_unsupported_platform(self):
        publish = Mock()
        manager = DebugConsoleManager(publish=publish)
        with patch("utils.debug_console.sys.platform", "linux"):
            manager.handle_keyboard_event(SimpleNamespace(key="F12"))
        publish.assert_called_once_with({
            "type": "status",
            "text": "Debug console is currently supported on Windows",
            "color": "orange",
        })

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
