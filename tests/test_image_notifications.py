"""Notification images use local files and fail back to the existing text path."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from ui.system_tray import SystemTray
from utils.i18n import message, set_language
from utils.image_notifications import ImageNotifications


class ImageNotificationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "earbuds image.png"
        with Image.new("RGBA", (80, 40), (60, 70, 80, 255)) as image:
            image.save(self.path)
        self.addCleanup(set_language, "en")
        self.service = ImageNotifications()

    def test_missing_image_and_unsupported_platform_do_not_send(self):
        icon = Mock()
        with patch("utils.image_notifications.sys.platform", "win32"):
            self.assertFalse(self.service.show(icon, "body", "title", str(self.path.with_suffix(".missing")), Mock()))
        with patch("utils.image_notifications.sys.platform", "other"):
            self.assertFalse(self.service.show(icon, "body", "title", str(self.path), Mock()))
        icon._message.assert_not_called()

    def test_windows_custom_icon_keeps_tray_icon_and_reuses_owned_handle(self):
        if sys.platform != "win32":
            self.skipTest("Windows API wrapper test")
        from pystray._util import win32
        icon = SimpleNamespace(_hwnd=123, _message=Mock(), icon=object())
        original_icon = icon.icon
        with patch.object(win32, "LoadImage", return_value=456) as load, patch.object(win32, "DestroyIcon") as destroy:
            for _ in range(2):
                self.assertTrue(self.service.show(icon, "Connected", "Redmi Buds 6 Play", str(self.path), Mock()))
            self.assertEqual(load.call_count, 1)
            kwargs = icon._message.call_args.kwargs
            self.assertEqual(kwargs["hBalloonIcon"], 456)
            self.assertEqual(kwargs["dwInfoFlags"], 0x24)
            self.assertEqual(kwargs["szInfo"], "Connected")
            self.assertEqual(kwargs["szInfoTitle"], "Redmi Buds 6 Play")
            self.assertNotIn("hIcon", kwargs)
            self.assertIs(icon.icon, original_icon)
            destroy.assert_not_called()
            self.service.close()
            self.service.close()
            destroy.assert_called_once_with(456)

    def test_windows_long_unicode_text_fits_native_utf16_fields(self):
        if sys.platform != "win32":
            self.skipTest("Windows API wrapper test")
        from pystray._util import win32
        icon = SimpleNamespace(_hwnd=123, _message=Mock())
        with patch.object(win32, "LoadImage", return_value=456), patch.object(win32, "DestroyIcon"):
            self.assertTrue(self.service.show(icon, "😀" * 300, "😀" * 80, str(self.path), Mock()))
            values = icon._message.call_args.kwargs
            self.assertLessEqual(len(values["szInfo"].encode("utf-16-le")), 510)
            self.assertLessEqual(len(values["szInfoTitle"].encode("utf-16-le")), 126)
            self.service.close()

    def test_native_failure_returns_false_and_closes_handle_later(self):
        if sys.platform != "win32":
            self.skipTest("Windows API wrapper test")
        from pystray._util import win32
        icon = SimpleNamespace(_hwnd=123, _message=Mock(side_effect=OSError("shell unavailable")))
        with patch.object(win32, "LoadImage", return_value=456), patch.object(win32, "DestroyIcon") as destroy:
            self.assertFalse(self.service.show(icon, "body", "title", str(self.path), Mock()))
            self.service.close()
            destroy.assert_called_once_with(456)

    def test_linux_delivery_runs_on_glib_loop_and_falls_back_once_on_error(self):
        glib = Mock()
        notifier = Mock()
        icon = SimpleNamespace(_notifier=notifier)
        fallback = Mock()
        modules = {"gi": Mock(), "gi.repository": SimpleNamespace(GLib=glib)}
        with patch.dict(sys.modules, modules), patch("utils.image_notifications.sys.platform", "linux"):
            self.assertTrue(self.service.show(icon, "body", "title", str(self.path), fallback))
            notifier.notify.assert_not_called()
            callback = glib.idle_add.call_args.args[0]
            self.assertFalse(callback())
            notifier.notify.assert_called_once_with("title", "body", str(self.path.resolve()))
            fallback.assert_not_called()
            notifier.notify.side_effect = OSError("dbus unavailable")
            self.assertTrue(self.service.show(icon, "body", "title", str(self.path), fallback))
            self.assertFalse(glib.idle_add.call_args.args[0]())
            fallback.assert_called_once_with()

    def test_linux_invalid_picture_is_not_scheduled_and_close_cancels_delivery(self):
        glib = Mock()
        notifier = Mock()
        modules = {"gi": Mock(), "gi.repository": SimpleNamespace(GLib=glib)}
        with patch.dict(sys.modules, modules), patch("utils.image_notifications.sys.platform", "linux"):
            self.assertTrue(self.service.show(SimpleNamespace(_notifier=notifier), "body", "title", str(self.path), Mock()))
            self.service.close()
            self.assertFalse(glib.idle_add.call_args.args[0]())
            notifier.notify.assert_not_called()
            self.service = ImageNotifications()
            self.path.write_bytes(b"not a picture")
            glib.reset_mock()
            self.assertFalse(self.service.show(SimpleNamespace(_notifier=notifier), "body", "title", str(self.path), Mock()))
            glib.idle_add.assert_not_called()

    def test_tray_connection_uses_model_and_cached_picture_without_changing_icon(self):
        tray = SystemTray(Mock(), Mock())
        tray.icon = Mock()
        tray._image_notifications = Mock()
        tray.set_device("Redmi Buds 6 Play", str(self.path))
        tray.set_device("", "")  # disconnect presentation does not erase the cache
        set_language("tr")
        tray.notify(message("tray.connected"), device=True, silent=False)
        args = tray._image_notifications.show.call_args.args
        self.assertEqual(args[:4], (tray.icon, "Kulaklık bağlandı", "Redmi Buds 6 Play", str(self.path)))
        tray.icon.notify.assert_not_called()
        tray.icon.icon = Mock()
        set_language("zh-CN")
        args[4]()  # asynchronous error path uses the language captured at send time
        tray.icon.notify.assert_called_once_with("Kulaklık bağlandı", "Redmi Buds 6 Play")

    def test_tray_falls_back_when_image_fails_or_is_absent(self):
        tray = SystemTray(Mock(), Mock())
        tray.icon = Mock()
        tray._image_notifications = Mock()
        tray._image_notifications.show.return_value = False
        tray.set_device("Redmi Buds 6 Play", str(self.path))
        tray.notify("Connected", device=True, silent=False)
        tray.icon.notify.assert_called_once_with("Connected", "Redmi Buds 6 Play")
        tray.set_device("Redmi Buds 6 Play", "")
        tray._image_notifications.show.reset_mock()
        tray.notify("Connected", device=True, silent=False)
        tray._image_notifications.show.assert_not_called()
        tray.notify("Disconnected", silent=False)
        self.assertEqual(tray.icon.notify.call_args.args, ("Disconnected", "Mi Buds Client"))

    def test_every_default_notification_and_image_fallback_stay_silent(self):
        tray = SystemTray(Mock(), Mock())
        tray.icon = Mock()
        tray._image_notifications = Mock()
        tray._image_notifications.show.return_value = True
        for body in ("Connected", "Disconnected", "Placed in case", "Removed from case"):
            tray.notify(body)
            self.assertTrue(tray._image_notifications.show.call_args.kwargs["silent"])
        tray.set_device("Redmi Buds 6 Play", str(self.path))
        tray._image_notifications.show.side_effect = [False, True]
        tray.notify("Connected", device=True)
        self.assertEqual(tray._image_notifications.show.call_args.args[3], "")
        self.assertTrue(tray._image_notifications.show.call_args.kwargs["silent"])
        tray.icon.notify.assert_not_called()
        tray._image_notifications.show.side_effect = None
        tray._image_notifications.show.return_value = False
        tray.notify("Disconnected")
        tray.icon.notify.assert_not_called()

    def test_windows_quiet_flag_on_both_native_image_and_text(self):
        if sys.platform != "win32":
            self.skipTest("Windows API wrapper test")
        from pystray._util import win32
        icon = SimpleNamespace(_hwnd=123, _message=Mock())
        with patch.object(win32, "LoadImage", return_value=456), patch.object(win32, "DestroyIcon"):
            self.assertTrue(self.service.show(icon, "body", "title", str(self.path), Mock(), silent=True))
            self.assertEqual(icon._message.call_args.kwargs["dwInfoFlags"], 0x34)
            self.assertTrue(self.service.show(icon, "body", "title", "", Mock(), silent=True))
            self.assertEqual(icon._message.call_args.kwargs["dwInfoFlags"], 0x10)
            self.service.close()

    def test_linux_quiet_hint_on_native_image_and_text(self):
        glib = Mock()
        glib.Variant.side_effect = lambda signature, value: SimpleNamespace(signature=signature, value=value)
        gio = SimpleNamespace(DBusCallFlags=SimpleNamespace(NONE=0))
        notifier = SimpleNamespace(notify=Mock(), _notify=Mock(), _nid=0)
        notifier._notify.call_sync.return_value.unpack.return_value = (12,)
        modules = {"gi": Mock(), "gi.repository": SimpleNamespace(GLib=glib, Gio=gio)}
        with patch.dict(sys.modules, modules), patch("utils.image_notifications.sys.platform", "linux"):
            for path in (str(self.path), ""):
                self.assertTrue(self.service.show(SimpleNamespace(_notifier=notifier), "body", "title", path, Mock(), silent=True))
                self.assertFalse(glib.idle_add.call_args.args[0]())
                payload = notifier._notify.call_sync.call_args.args[1]
                hint = payload.value[6]["suppress-sound"]
                self.assertEqual((hint.signature, hint.value), ("b", True))
            notifier.notify.assert_not_called()
