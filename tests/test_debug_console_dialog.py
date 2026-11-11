"""Flet debug console lifecycle without a desktop or stream redirection."""
import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ui.components.debug_console import DebugConsoleDialog
from utils.debug_console import DebugConsoleManager
from utils.i18n import set_language, t


class DebugConsoleDialogTests(unittest.TestCase):
    def setUp(self):
        set_language('en')
        self.addCleanup(set_language, 'en')
        self.manager = DebugConsoleManager()
        self.page = SimpleNamespace(width=420, height=360, update=Mock(), run_task=Mock(), controls=[object()])
        self.page.show_dialog = Mock(side_effect=lambda dialog: setattr(dialog, 'open', True))
        self.console = DebugConsoleDialog(self.page, self.manager)

    def test_open_shows_history_and_schedules_live_refresh_without_rebuilding_page(self):
        self.manager._append_log('history\n', 'stdout')
        controls = self.page.controls
        self.assertEqual(self.console.toggle(), 'opened')
        self.assertTrue(self.console.dialog.open)
        self.assertEqual(self.console.text.value, 'history\n')
        self.assertTrue(self.console.text.selectable)
        self.assertEqual(self.console.text.font_family, 'monospace')
        self.page.run_task.assert_called_once_with(self.console._refresh_logs, 1)
        self.assertIs(self.page.controls, controls)
        self.assertLessEqual(self.console.body.width, self.page.width - 80)
        self.assertLessEqual(self.console.body.height, self.page.height - 180)

    def test_toggle_close_waits_for_native_dismissal_before_reopening(self):
        self.console.toggle()
        self.assertEqual(self.console.toggle(), 'closed')
        self.assertFalse(self.console.dialog.open)
        self.assertEqual(self.console.toggle(), 'closed')
        self.page.show_dialog.assert_called_once()
        self.console._dismissed()
        self.assertEqual(self.console.toggle(), 'opened')
        self.assertEqual(self.page.show_dialog.call_count, 2)

    def test_clear_resets_buffer_and_empty_state(self):
        self.manager._append_log('history\n', 'stdout')
        self.console.toggle()
        self.console.clear()
        self.assertEqual(self.manager.get_recent_logs(), '')
        self.assertEqual(self.console.text.value, t('debug.empty'))
        self.page.update.assert_called_once_with()

    def test_live_refresh_runs_on_ui_task_and_stops_on_shutdown(self):
        self.console.toggle()
        count = 0
        async def sleep(_):
            nonlocal count
            count += 1
            if count == 1:
                self.manager._append_log('new message\n', 'stderr')
            else:
                self.console.stop()
        with patch('ui.components.debug_console.asyncio.sleep', side_effect=sleep):
            asyncio.run(self.console._refresh_logs(1))
        self.assertEqual(self.console.text.value, '[ERR] new message\n')
        self.page.update.assert_called_once_with()
        self.assertEqual(self.console.toggle(), 'failed')

    def test_closed_or_stale_refresh_never_updates_page(self):
        self.console.toggle()
        self.console.close()
        self.page.update.reset_mock()
        with patch('ui.components.debug_console.asyncio.sleep'):
            asyncio.run(self.console._refresh_logs(1))
        self.page.update.assert_not_called()

    def test_unchanged_logs_do_not_generate_repeated_ui_updates(self):
        self.console.toggle()
        count = 0
        async def sleep(_):
            nonlocal count
            count += 1
            if count == 3:
                self.console.stop()
        with patch('ui.components.debug_console.asyncio.sleep', side_effect=sleep):
            asyncio.run(self.console._refresh_logs(1))
        self.page.update.assert_not_called()

    def test_reopen_updates_translations_without_translating_log_content(self):
        self.manager._append_log('Close\n', 'stdout')
        self.console.toggle()
        self.console.close()
        self.console._dismissed()
        set_language('tr')
        self.console.toggle()
        self.assertEqual(self.console.dialog.title.value, 'Debug Konsolu')
        self.assertEqual(self.console.dialog.actions[0].content, 'Temizle')
        self.assertEqual(self.console.text.value, 'Close\n')

    def test_shutdown_prevents_late_callbacks(self):
        self.console.stop()
        self.console.clear()
        self.console.close()
        self.assertEqual(self.console.toggle(), 'failed')
        self.page.update.assert_not_called()
        self.page.run_task.assert_not_called()

    def test_destroyed_session_does_not_escape_refresh_task(self):
        self.console.toggle()
        self.manager._append_log('late\n', 'stdout')
        self.page.update.side_effect = RuntimeError('An attempt to fetch destroyed session.')
        with patch('ui.components.debug_console.asyncio.sleep'):
            asyncio.run(self.console._refresh_logs(1))
        self.page.update.assert_called_once_with()
