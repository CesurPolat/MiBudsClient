"""A native visible flag alone does not prove that a desktop hosts the icon."""
from types import SimpleNamespace
import subprocess
import unittest
from unittest.mock import Mock, patch

from utils.tray_host import TrayHostMonitor
from ui.system_tray import SystemTray


class TrayHostTests(unittest.TestCase):
    def test_sni_host_property_is_required_and_alternative_namespace_is_supported(self):
        with patch('utils.tray_host.subprocess.run', side_effect=[
            SimpleNamespace(returncode=0, stdout='(<false>,)'),
            SimpleNamespace(returncode=0, stdout='(<true>,)'),
        ]) as run:
            self.assertTrue(TrayHostMonitor._indicator_host())
        self.assertEqual(run.call_count, 2)
        self.assertIn('org.freedesktop.StatusNotifierWatcher', run.call_args.args[0])

    def test_unavailable_or_slow_watcher_is_not_a_working_host(self):
        for result in (FileNotFoundError(), subprocess.TimeoutExpired('gdbus', 1),
                       SimpleNamespace(returncode=1, stdout=''), SimpleNamespace(returncode=0, stdout='(<false>,)')):
            with self.subTest(result=result), patch('utils.tray_host.subprocess.run') as run:
                if isinstance(result, Exception):
                    run.side_effect = result
                else:
                    run.return_value = result
                self.assertFalse(TrayHostMonitor._indicator_host())

    def test_gtk_embedded_state_and_late_probe_after_stop(self):
        icon = SimpleNamespace(_status_icon=Mock())
        callback = Mock()
        monitor = TrayHostMonitor(icon, callback)
        icon._status_icon.is_embedded.return_value = False
        self.assertFalse(monitor._gtk_probe())
        callback.assert_called_once_with(False)
        icon._status_icon.is_embedded.return_value = True
        monitor._gtk_probe()
        callback.assert_called_with(True)
        monitor.stop()
        callback.reset_mock()
        monitor._gtk_probe()
        callback.assert_not_called()

    def test_host_loss_restores_window_and_recovery_reenables_hiding(self):
        tray = SystemTray(Mock(), Mock())
        icon = tray.icon = Mock()
        tray._host_state(icon, False)
        tray.on_show.assert_not_called()
        tray._host_state(icon, True)
        self.assertTrue(tray.available)
        tray._host_state(icon, False)
        self.assertFalse(tray.available)
        tray.on_show.assert_called_once()
        tray._host_state(icon, True)
        self.assertTrue(tray.available)
        tray._host_state(Mock(), False)
        self.assertTrue(tray.available)
        tray.stop()
        tray._host_state(icon, True)
        self.assertFalse(tray.available)
