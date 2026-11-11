"""Desktop dependencies and native tray errors must not strand the window."""
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import flet as ft
from tray_fakes import fake_tray_api
from utils import tray_backend
from ui.system_tray import SystemTray
from ui.window_manager import WindowManager


class TrayLoaderTests(unittest.TestCase):
    def test_ayatana_is_accepted_when_appindicator_namespace_is_missing(self):
        gi = Mock()
        gi.require_version.side_effect = [ValueError('missing AppIndicator3'), None]
        with patch.object(tray_backend, '_ensure_gi_module', return_value=True), patch.dict(
            'sys.modules', {'gi': gi},
        ), patch.object(tray_backend.importlib, 'import_module') as load:
            self.assertTrue(tray_backend._has_appindicator_namespace())
        load.assert_called_once_with('gi.repository.AyatanaAppIndicator3')

    def test_import_failures_try_remaining_linux_backends_and_restore_environment(self):
        api = object()
        selected = []
        def load(name):
            self.assertEqual(name, 'pystray')
            selected.append(os.environ['PYSTRAY_BACKEND'])
            if len(selected) < 3:
                raise ValueError('native dependency unavailable')
            return api
        with patch.object(tray_backend.sys, 'platform', 'linux'), patch.dict(
            os.environ, {'DISPLAY': ':1'}, clear=True,
        ), patch.object(tray_backend, '_has_gtk_namespace', return_value=True), patch.object(
            tray_backend, '_has_appindicator_namespace', return_value=True,
        ), patch.object(tray_backend.importlib, 'import_module', side_effect=load):
            self.assertIs(tray_backend.load_tray_module(), api)
            self.assertNotIn('PYSTRAY_BACKEND', os.environ)
        self.assertEqual(selected, ['appindicator', 'gtk', 'xorg'])

    def test_missing_gtk_and_display_are_nonfatal_without_importing_pystray(self):
        with patch.object(tray_backend.sys, 'platform', 'linux'), patch.dict(os.environ, {}, clear=True), patch.object(
            tray_backend, '_has_gtk_namespace', return_value=False,
        ), patch.object(tray_backend.importlib, 'import_module') as load:
            self.assertIsNone(tray_backend.load_tray_module())
        load.assert_not_called()

    def test_explicit_backend_is_preserved_even_when_it_fails(self):
        with patch.object(tray_backend.sys, 'platform', 'linux'), patch.dict(
            os.environ, {'PYSTRAY_BACKEND': 'gtk'}, clear=True,
        ), patch.object(tray_backend.importlib, 'import_module', side_effect=ImportError('missing GTK')) as load:
            self.assertIsNone(tray_backend.load_tray_module())
            self.assertEqual(os.environ['PYSTRAY_BACKEND'], 'gtk')
        load.assert_called_once_with('pystray')

    def test_windows_uses_default_pystray_selection_without_linux_probes(self):
        with patch.object(tray_backend.sys, 'platform', 'win32'), patch.dict(os.environ, {}, clear=True), patch.object(
            tray_backend, '_has_gtk_namespace', side_effect=AssertionError('Linux probe on Windows'),
        ), patch.object(tray_backend.importlib, 'import_module') as load:
            self.assertIs(tray_backend.load_tray_module(), load.return_value)
        load.assert_called_once_with('pystray')


class TrayLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tray = SystemTray(Mock(), Mock())
        self.tray._linux_notifications = Mock()
        self.api = fake_tray_api()
        self.notifications = Mock()
        self.tray._image_notifications = self.notifications
        self.context = patch('ui.system_tray.pystray', self.api)
        self.context.start()
        self.addCleanup(self.context.stop)
        self.image_context = patch('ui.system_tray.load_pil_image', return_value=Mock())
        self.image_context.start()
        self.addCleanup(self.image_context.stop)

    def test_missing_pystray_keeps_application_running(self):
        with patch('ui.system_tray.pystray', None):
            self.tray.run()
            self.tray.refresh_menu()
            self.tray.notify('test')
            self.tray.stop()
        self.assertFalse(self.tray.available)
        self.api.Icon.assert_not_called()

    def test_ready_only_inside_native_loop_and_unexpected_exit_restores_window(self):
        def run(setup):
            self.assertFalse(self.tray.available)
            setup(self.api.Icon.return_value)
            self.assertTrue(self.tray.available)
        self.api.Icon.return_value.run.side_effect = run
        self.tray.run()
        self.assertFalse(self.tray.available)
        self.assertIsNone(self.tray.icon)
        self.tray.on_show.assert_called_once()
        self.notifications.close.assert_called_once()

    def test_native_loop_failure_restores_window_and_releases_notifications(self):
        def run(setup):
            setup(self.api.Icon.return_value)
            raise RuntimeError('native loop failed')
        self.api.Icon.return_value.run.side_effect = run
        self.tray.run()
        self.assertFalse(self.tray.available)
        self.tray.on_show.assert_called_once()
        self.notifications.close.assert_called_once()

    def test_menu_and_notification_binding_errors_do_not_escape(self):
        self.notifications.bind.side_effect = RuntimeError('notification hook unavailable')
        self.api.Icon.return_value.update_menu.side_effect = RuntimeError('menu failed')
        def run(setup):
            setup(self.api.Icon.return_value)
            self.tray.refresh_menu()
            self.assertTrue(self.tray.available)
            self.tray.stop()
        self.api.Icon.return_value.run.side_effect = run
        self.tray.run()
        self.tray.on_show.assert_not_called()
        self.api.Icon.return_value.stop.assert_called_once()

    def test_shutdown_before_run_never_creates_an_icon(self):
        self.tray.stop()
        self.tray.run()
        self.api.Icon.assert_not_called()
        self.tray.on_show.assert_not_called()


class WindowTrayFallbackTests(unittest.TestCase):
    def test_close_keeps_taskbar_access_until_tray_ready_on_both_platforms(self):
        for platform in (ft.PagePlatform.WINDOWS, ft.PagePlatform.LINUX):
            with self.subTest(platform=platform):
                page = SimpleNamespace(window=ft.Window(), platform=platform, update=Mock(),
                                       run_task=Mock(), pubsub=Mock())
                manager = WindowManager(page)
                manager.apply_hide()
                self.assertTrue(page.window.visible)
                self.assertTrue(page.window.minimized)
                self.assertFalse(page.window.skip_task_bar)
                manager.tray_available = lambda: True
                manager.apply_hide()
                self.assertFalse(page.window.visible)
                self.assertTrue(page.window.skip_task_bar)
                self.assertFalse(page.window.minimized)
