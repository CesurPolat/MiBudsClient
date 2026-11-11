"""Automatic setup uses a temporary home and fake commands, never the real Shell."""
import ast
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from utils import wayland_setup as setup


class WaylandSetupTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / 'bundle/assets/gnome-extension' / setup.UUID
        self.source.mkdir(parents=True)
        for name in ('extension.js', 'metadata.json'):
            (self.source / name).write_text('bundled ' + name)
        self.target = self.root / 'user/gnome-shell/extensions' / setup.UUID
        self.enabled = ['other-extension@example.com']
        self.disabled = []
        self.global_disable = False
        self.warm = False
        self.calls = []
        for context in (
            patch.object(setup.sys, 'platform', 'linux'),
            patch.dict(os.environ, {'XDG_DATA_HOME': str(self.root / 'user'), 'XDG_SESSION_TYPE': 'wayland',
                                    'WAYLAND_DISPLAY': 'wayland-0', 'XDG_CURRENT_DESKTOP': 'zorin:GNOME'}, clear=True),
            patch.object(setup.sys, '_MEIPASS', str(self.root / 'bundle'), create=True),
            patch.object(setup, '_run', side_effect=self.run_command),
            patch.object(setup.shutil, 'which', return_value='/usr/bin/gdbus'),
            patch.object(setup, 'detect_gnome_fullscreen', return_value=(None, '')),
        ):
            context.start()
            self.addCleanup(context.stop)

    def run_command(self, command):
        self.calls.append(command)
        if command == ['gnome-shell', '--version']:
            return SimpleNamespace(stdout='GNOME Shell 46.0\n')
        if command[:3] == ['gsettings', 'get', 'org.gnome.shell']:
            values = {'enabled-extensions': repr(self.enabled), 'disabled-extensions': repr(self.disabled),
                      'disable-user-extensions': str(self.global_disable).lower()}
            return SimpleNamespace(stdout=values[command[3]])
        if command[:3] == ['gsettings', 'set', 'org.gnome.shell']:
            self.assertEqual(command[3], 'enabled-extensions')
            self.enabled = ast.literal_eval(command[4])
            return SimpleNamespace(stdout='')
        if command[:2] == ['gnome-extensions', 'enable']:
            if not self.warm:
                raise subprocess.CalledProcessError(2, command, stderr='Extension does not exist')
            self.enabled.append(setup.UUID)
            return SimpleNamespace(stdout='')
        raise AssertionError(command)

    def test_first_login_installs_from_bundle_and_schedules_activation_without_losing_other_extensions(self):
        self.assertEqual(setup.ensure_gnome_bridge(), 'relogin')
        self.assertEqual(self.enabled, ['other-extension@example.com', setup.UUID])
        for name in ('extension.js', 'metadata.json'):
            self.assertEqual((self.target / name).read_bytes(), (self.source / name).read_bytes())
        self.assertTrue(json.loads((self.target / '.mibuds-setup.json').read_text())['registered'])

    def test_discovered_extension_activates_immediately(self):
        self.warm = True
        with patch.object(setup, 'detect_gnome_fullscreen', return_value=(False, 'terminal')):
            self.assertEqual(setup.ensure_gnome_bridge(), 'ready')
        self.assertFalse(any(command[:2] == ['gsettings', 'set'] for command in self.calls))

    def test_repeated_launch_does_not_rewrite_files_or_extension_settings(self):
        setup.ensure_gnome_bridge()
        self.calls.clear()
        with patch.object(setup, '_write_file') as write, patch.object(setup, 'detect_gnome_fullscreen', return_value=(False, '')):
            self.assertEqual(setup.ensure_gnome_bridge(), 'ready')
        write.assert_not_called()
        self.assertFalse(any(command[0] == 'gnome-extensions' or command[1] == 'set' for command in self.calls))

    def test_changed_extension_is_updated_and_requires_relogin(self):
        setup.ensure_gnome_bridge()
        (self.source / 'extension.js').write_text('new version')
        with patch.object(setup, 'detect_gnome_fullscreen', return_value=(True, 'game')):
            self.assertEqual(setup.ensure_gnome_bridge(), 'relogin')
        self.assertEqual((self.target / 'extension.js').read_text(), 'new version')

    def test_later_manual_disable_is_respected(self):
        setup.ensure_gnome_bridge()
        self.enabled.remove(setup.UUID)
        self.calls.clear()
        self.assertEqual(setup.ensure_gnome_bridge(), 'disabled')
        self.assertFalse(any(command[0] == 'gnome-extensions' or command[1] == 'set' for command in self.calls))

    def test_global_and_explicit_extension_disables_are_not_overridden(self):
        for global_disable, disabled in ((True, []), (False, [setup.UUID])):
            self.global_disable, self.disabled = global_disable, disabled
            self.assertEqual(setup.ensure_gnome_bridge(), 'disabled')
            self.assertFalse(self.target.exists())

    def test_windows_and_x11_never_probe_or_install_gnome_extensions(self):
        for platform, session in (('win32', 'wayland'), ('linux', 'x11')):
            with self.subTest(platform=platform, session=session), patch.object(setup.sys, 'platform', platform), patch.dict(
                os.environ, {'XDG_SESSION_TYPE': session, 'WAYLAND_DISPLAY': ''},
            ):
                self.assertEqual(setup.ensure_gnome_bridge(), 'not_needed')
        self.assertEqual(self.calls, [])
        self.assertFalse(self.target.exists())

    def test_unsupported_desktop_or_gnome_version_is_nonfatal(self):
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'KDE'}):
            self.assertEqual(setup.ensure_gnome_bridge(), 'unavailable')
        self.assertEqual(self.calls, [])
        with patch.object(setup, '_run', return_value=SimpleNamespace(stdout='GNOME Shell 49.0')):
            self.assertEqual(setup.ensure_gnome_bridge(), 'unavailable')
        self.assertFalse(self.target.exists())

    def test_missing_tools_timeout_readonly_directory_and_locked_settings_do_not_crash(self):
        for failure in (FileNotFoundError(), subprocess.TimeoutExpired('gnome-shell', 3)):
            with patch.object(setup, '_run', side_effect=failure):
                self.assertEqual(setup.ensure_gnome_bridge(), 'unavailable')
        with patch.object(setup, '_write_file', side_effect=PermissionError('read only')):
            self.assertEqual(setup.ensure_gnome_bridge(), 'unavailable')
        original = self.run_command
        def locked(command):
            if command[:2] == ['gsettings', 'set']:
                raise subprocess.CalledProcessError(1, command)
            return original(command)
        with patch.object(setup, '_run', side_effect=locked):
            self.assertEqual(setup.ensure_gnome_bridge(), 'unavailable')
        self.assertFalse((self.target / '.mibuds-setup.json').exists())

    def test_missing_bundle_does_not_register_partial_extension(self):
        (self.source / 'metadata.json').unlink()
        self.assertEqual(setup.ensure_gnome_bridge(), 'unavailable')
        self.assertFalse(self.target.exists())
        self.assertNotIn(setup.UUID, self.enabled)

    def test_missing_dbus_client_does_not_suggest_relogin_or_install_files(self):
        with patch.object(setup.shutil, 'which', return_value=None):
            self.assertEqual(setup.ensure_gnome_bridge(), 'unavailable')
        self.assertFalse(self.target.exists())
        self.assertEqual(self.calls, [])

    def test_empty_gvariant_extension_array_is_supported(self):
        with patch.object(setup, '_run', return_value=SimpleNamespace(stdout='@as []\n')):
            self.assertEqual(setup._extension_list('enabled-extensions'), [])

    def test_settings_write_must_be_retained_before_marking_setup_complete(self):
        original = self.run_command
        def ignored(command):
            if command[:2] == ['gsettings', 'set']:
                return SimpleNamespace(stdout='')
            return original(command)
        with patch.object(setup, '_run', side_effect=ignored):
            self.assertEqual(setup.ensure_gnome_bridge(), 'unavailable')
        self.assertFalse((self.target / '.mibuds-setup.json').exists())
