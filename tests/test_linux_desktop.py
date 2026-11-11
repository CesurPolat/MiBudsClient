"""Linux desktop identity uses a temporary data home, never the real menu."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils import linux_desktop as desktop

_real_legacy_client = desktop._legacy_client


class LinuxDesktopTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.image = self.root / 'bundle/assets/icon.png'
        self.image.parent.mkdir(parents=True)
        self.image.write_bytes(b'fixture icon')
        for context in (
            patch.object(desktop.sys, 'platform', 'linux'),
            patch.dict(os.environ, {'XDG_DATA_HOME': str(self.root / 'data'),
                                    'XDG_DATA_DIRS': str(self.root / 'system')}, clear=True),
            patch.object(desktop, 'get_resource_path', return_value=str(self.image)),
            patch.object(desktop, '_legacy_client', return_value=True),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.entries = self.root / 'data/applications'

    def test_legacy_identity_and_icon_are_registered_and_removed_after_exit(self):
        cleanup = desktop.setup_linux_desktop()
        legacy = self.entries / (desktop.LEGACY_ID + '.desktop')
        content = legacy.read_text()
        self.assertIn('Name=MiBudsClient', content)
        self.assertIn('NoDisplay=true', content)
        self.assertIn('StartupWMClass=flet', content)
        icon = self.root / 'data/MiBudsClient/icon.png'
        self.assertIn(f'Icon={icon}', content)
        self.assertEqual(icon.read_bytes(), b'fixture icon')
        self.assertEqual(os.environ['FLET_APP_ID'], desktop.APP_ID)
        cleanup()
        self.assertFalse(legacy.exists())
        self.assertFalse((self.entries / (desktop.APP_ID + '.desktop')).exists())
        self.assertTrue(icon.is_file())

    def test_appimage_command_uses_original_file_not_temporary_mount(self):
        appimage = self.root / 'My App.AppImage'
        appimage.write_bytes(b'fixture')
        with patch.dict(os.environ, {'APPIMAGE': str(appimage)}):
            cleanup = desktop.setup_linux_desktop()
        self.assertIn(f'Exec="{appimage}"', (self.entries / (desktop.APP_ID + '.desktop')).read_text())
        cleanup()

    def test_user_entry_is_never_overwritten_and_cleanup_respects_edits(self):
        self.entries.mkdir(parents=True)
        legacy = self.entries / (desktop.LEGACY_ID + '.desktop')
        legacy.write_text('[Desktop Entry]\nName=Another application\n')
        cleanup = desktop.setup_linux_desktop()
        own = self.entries / (desktop.APP_ID + '.desktop')
        own.write_text('[Desktop Entry]\nName=User edited\n')
        cleanup()
        self.assertIn('Another application', legacy.read_text())
        self.assertIn('User edited', own.read_text())

    def test_system_entry_is_never_shadowed(self):
        system = self.root / 'system/applications' / (desktop.LEGACY_ID + '.desktop')
        system.parent.mkdir(parents=True)
        system.write_text('system entry')
        cleanup = desktop.setup_linux_desktop()
        self.assertFalse((self.entries / system.name).exists())
        cleanup()
        self.assertEqual(system.read_text(), 'system entry')

    def test_modern_flet_has_own_identity_without_shared_alias(self):
        with patch.object(desktop, '_legacy_client', return_value=False):
            cleanup = desktop.setup_linux_desktop()
        self.assertFalse((self.entries / (desktop.LEGACY_ID + '.desktop')).exists())
        content = (self.entries / (desktop.APP_ID + '.desktop')).read_text()
        self.assertIn('StartupWMClass=' + desktop.APP_ID, content)
        cleanup()

    def test_missing_assets_do_not_prevent_startup(self):
        self.image.unlink()
        cleanup = desktop.setup_linux_desktop()
        cleanup()
        self.assertFalse(self.entries.exists())

    def test_windows_does_not_write_files_or_change_identity(self):
        with patch.object(desktop.sys, 'platform', 'win32'):
            cleanup = desktop.setup_linux_desktop()
        cleanup()
        self.assertNotIn('FLET_APP_ID', os.environ)
        self.assertFalse(self.entries.exists())

    def test_flet_version_detection_does_not_require_distribution_metadata(self):
        for version, expected in (('0.82.2', True), ('1.1.2', False)):
            with self.subTest(version=version), patch('flet_desktop.version.version', version):
                self.assertEqual(_real_legacy_client(), expected)
        with patch('flet_desktop.version.version', 'unknown'):
            with self.assertRaises(ValueError):
                _real_legacy_client()
