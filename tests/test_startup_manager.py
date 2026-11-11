"""Login registration and repair without changing the user's startup settings."""
import configparser
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

from utils import startup_manager as startup
from utils.resource_manager import get_resource_path


class LinuxStartupTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for context in (
            patch.object(startup.platform, 'system', return_value='Linux'),
            patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root)}),
            patch.object(startup, 'get_executable_path', return_value='/opt/My Buds/main.py'),
            patch.object(startup.sys, 'executable', '/opt/My Buds/venv/bin/python'),
            patch.object(startup.sys, 'frozen', False, create=True),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.path = Path(startup._get_linux_autostart_path())

    def write(self, content):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content, encoding='utf-8')

    def read(self):
        entry = configparser.ConfigParser(interpolation=None)
        entry.optionxform = str
        entry.read(self.path, encoding='utf-8')
        return entry['Desktop Entry']

    def test_source_registration_includes_venv_and_working_directory(self):
        self.assertTrue(startup.set_startup(True))
        entry = self.read()
        self.assertEqual(entry['Exec'], '"/opt/My Buds/venv/bin/python" "/opt/My Buds/main.py"')
        self.assertEqual(entry['Path'], '/opt/My Buds')
        self.assertTrue(startup.is_startup_enabled())
        self.assertTrue(startup.set_startup(False))
        self.assertFalse(self.path.exists())
        self.assertFalse(startup.reconcile_startup())
        self.assertFalse(self.path.exists())

    def test_binary_registration_does_not_include_python(self):
        with patch.object(startup.sys, 'frozen', True), patch.object(
            startup, 'get_executable_path', return_value='/opt/My Buds/MiBudsClient',
        ):
            self.assertTrue(startup.set_startup(True))
            self.assertEqual(self.read()['Exec'], '"/opt/My Buds/MiBudsClient"')

    def test_old_registration_is_repaired_once_and_keeps_desktop_preferences(self):
        self.write('[Desktop Entry]\nType=Application\nExec="/old/main.py"\nOnlyShowIn=KDE;\n')
        self.assertTrue(startup.reconcile_startup())
        entry = self.read()
        self.assertEqual(entry['OnlyShowIn'], 'KDE;')
        self.assertEqual(entry['Exec'], '"/opt/My Buds/venv/bin/python" "/opt/My Buds/main.py"')
        with patch.object(startup, '_write_desktop_file') as write:
            self.assertTrue(startup.reconcile_startup())
        write.assert_not_called()

    def test_enabled_entry_with_missing_command_is_repaired(self):
        self.write('[Desktop Entry]\nType=Application\n')
        self.assertTrue(startup.reconcile_startup())
        self.assertIn('main.py', self.read()['Exec'])

    def test_disabled_and_malformed_entries_are_not_enabled(self):
        for content in (
            '[Desktop Entry]\nHidden=true\nExec=/old/app\n',
            '[Desktop Entry]\nX-GNOME-Autostart-enabled=false\nExec=/old/app\n',
            '[Desktop Entry]\nHidden=invalid\n',
            'not a desktop entry',
        ):
            with self.subTest(content=content):
                self.write(content)
                self.assertFalse(startup.reconcile_startup())
                self.assertEqual(self.path.read_text(), content)

    def test_failed_atomic_repair_keeps_original_registration_and_cleans_temporary_file(self):
        content = '[Desktop Entry]\nType=Application\nExec=/old/app\n'
        self.write(content)
        with patch.object(startup.os, 'replace', side_effect=PermissionError('read only')), patch('builtins.print') as log:
            startup.reconcile_startup()
        self.assertTrue(log.called)
        self.assertEqual(self.path.read_text(), content)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_relative_xdg_config_path_uses_home_default(self):
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': 'relative'}), patch.object(
            startup.os.path, 'expanduser', return_value='/home/example/.config',
        ):
            self.assertEqual(startup._get_linux_autostart_path(), '/home/example/.config/autostart/mibudsclient.desktop')

    def test_exec_escapes_percent_and_reserved_characters_without_a_shell(self):
        # Expected on-disk escaping includes desktop-string and Exec layers.
        self.assertEqual(startup._desktop_argument('/opt/100%/buds'), '"/opt/100%%/buds"')
        self.assertEqual(startup._desktop_argument('/opt/$buds'), '"/opt/\\\\$buds"')
        self.assertEqual(startup._desktop_argument('/opt/"buds'), '"/opt/\\\\"buds"')
        self.assertEqual(startup._desktop_argument('/opt/\\buds'), '"/opt/\\\\\\\\buds"')
        for value in ('bad\npath', 'bad\rpath', 'bad\0path'):
            with self.assertRaises(ValueError):
                startup._desktop_argument(value)


class WindowsStartupTests(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock(REG_SZ=1, KEY_READ=2, KEY_SET_VALUE=4)
        self.key = self.registry.OpenKey.return_value.__enter__.return_value
        for context in (
            patch.object(startup.platform, 'system', return_value='Windows'),
            patch.object(startup, 'winreg', self.registry, create=True),
            patch.object(startup, 'get_executable_path', return_value=r'C:\My Buds\main.py'),
            patch.object(startup.sys, 'executable', r'C:\My Buds\venv\python.exe'),
            patch.object(startup.sys, 'frozen', False, create=True),
        ):
            context.start()
            self.addCleanup(context.stop)

    def test_source_registration_uses_windows_argument_quoting(self):
        self.assertTrue(startup.set_startup(True))
        self.registry.SetValueEx.assert_called_once_with(
            self.key, startup.APP_NAME, 0, 1,
            '"C:\\My Buds\\venv\\python.exe" "C:\\My Buds\\main.py"',
        )
        self.registry.OpenKey.return_value.__exit__.assert_called_once()

    def test_existing_registration_is_repaired_but_current_one_is_not_rewritten(self):
        self.registry.QueryValueEx.return_value = ('old command', 1)
        self.assertTrue(startup.reconcile_startup())
        self.registry.SetValueEx.assert_called_once()
        self.registry.SetValueEx.reset_mock()
        self.registry.QueryValueEx.return_value = (subprocess.list2cmdline(startup._startup_arguments()), 1)
        self.assertTrue(startup.reconcile_startup())
        self.registry.SetValueEx.assert_not_called()

    def test_missing_registration_is_not_created(self):
        self.registry.QueryValueEx.side_effect = FileNotFoundError()
        self.assertFalse(startup.reconcile_startup())
        self.registry.SetValueEx.assert_not_called()

    def test_packaged_registration_launches_only_executable(self):
        with patch.object(startup.sys, 'frozen', True):
            self.assertTrue(startup.set_startup(True))
        self.assertEqual(self.registry.SetValueEx.call_args.args[-1], '"C:\\My Buds\\main.py"')


class ResourcePathTests(unittest.TestCase):
    def test_source_assets_do_not_depend_on_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            try:
                os.chdir(directory)
                self.assertTrue(Path(get_resource_path('assets/icon.png')).is_file())
            finally:
                os.chdir(previous)

    def test_packaged_assets_use_bundle_directory(self):
        with patch('utils.resource_manager.sys._MEIPASS', '/tmp/example-bundle', create=True):
            self.assertEqual(get_resource_path('assets/icon.png'), '/tmp/example-bundle/assets/icon.png')
