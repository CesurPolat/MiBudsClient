"""Window RPCs must not outlive the Flet session or escape task callbacks."""
import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
from ui.window_manager import WindowManager


class WindowShutdownTests(unittest.TestCase):
    def setUp(self):
        sound_patch = patch('ui.window_manager.play_exit_melody')
        self.exit_melody = sound_patch.start()
        self.addCleanup(sound_patch.stop)

    def manager(self):
        page = SimpleNamespace(
            window=SimpleNamespace(close=AsyncMock(), destroy=AsyncMock(), to_front=AsyncMock()),
            platform=ft.PagePlatform.WINDOWS, update=Mock(), run_task=Mock(), pubsub=Mock(),
        )
        manager = WindowManager(page)
        manager._force_exit_after_delay = Mock()
        manager.show_closing_screen = Mock()
        return manager, page

    def run_scheduled(self, page):
        asyncio.run(page.run_task.call_args.args[0]())

    def test_session_close_notification_does_not_request_another_window_close(self):
        manager, page = self.manager()
        page.on_close(None)
        manager.close()
        manager.show()
        manager.hide()
        manager.apply_show()
        manager.apply_hide()
        page.update.assert_not_called()
        page.run_task.assert_not_called()
        page.pubsub.send_all.assert_not_called()
        manager.show_closing_screen.assert_not_called()
        self.assertTrue(manager._session_closed)

    def test_close_is_idempotent_and_runs_one_window_rpc(self):
        manager, page = self.manager()
        manager.close()
        manager.close()
        page.run_task.assert_called_once()
        self.run_scheduled(page)
        page.window.close.assert_awaited_once()
        page.window.destroy.assert_not_awaited()
        self.assertFalse(page.window.prevent_close)
        self.exit_melody.assert_called_once_with()

    def test_session_destroyed_before_queued_task_runs(self):
        manager, page = self.manager()
        manager.close()
        page.on_close(None)
        self.run_scheduled(page)
        page.window.close.assert_not_awaited()
        page.window.destroy.assert_not_awaited()
        page.update.assert_not_called()

    def test_session_destroyed_during_close_is_expected(self):
        manager, page = self.manager()
        page.window.close.side_effect = RuntimeError('An attempt to fetch destroyed session.')
        manager.close()
        with patch('builtins.print') as output:
            self.run_scheduled(page)
        output.assert_not_called()
        page.window.destroy.assert_not_awaited()
        self.assertTrue(manager._session_closed)

    def test_real_close_failure_awaits_destroy_fallback(self):
        manager, page = self.manager()
        page.window.close.side_effect = RuntimeError('native close failed')
        manager.close()
        with patch('builtins.print') as output:
            self.run_scheduled(page)
        page.window.destroy.assert_awaited_once()
        output.assert_called_once()

    def test_async_failure_is_handled_inside_the_scheduled_coroutine(self):
        manager, page = self.manager()
        page.window.to_front.side_effect = RuntimeError('native focus failed')
        self.assertTrue(manager._run_window_async(page.window.to_front))
        with patch('builtins.print') as output:
            self.run_scheduled(page)
        output.assert_called_once()

    def test_destroyed_session_during_scheduling_is_silent(self):
        manager, page = self.manager()
        page.run_task.side_effect = RuntimeError('An attempt to fetch destroyed session.')
        with patch('builtins.print') as output:
            self.assertFalse(manager._run_window_async(page.window.to_front))
        output.assert_not_called()
        self.assertTrue(manager._session_closed)

    def test_title_bar_close_still_hides_to_tray(self):
        manager, page = self.manager()
        page.window.on_event(SimpleNamespace(type=ft.WindowEventType.CLOSE))
        page.pubsub.send_all.assert_called_once_with({'type': 'window', 'action': 'hide'})
        self.assertFalse(manager._is_closing)
        self.exit_melody.assert_not_called()


if __name__ == '__main__':
    unittest.main()
