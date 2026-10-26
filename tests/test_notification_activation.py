"""Native notification activation reuses the existing Flet window-show callback."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ui.system_tray import SystemTray
from ui.window_manager import WindowManager
from utils.image_notifications import ImageNotifications


class NotificationActivationTests(unittest.TestCase):
    def test_activation_publishes_existing_window_show_route(self):
        page = SimpleNamespace(window=Mock(), pubsub=Mock())
        manager = WindowManager(page)
        tray = SystemTray(manager.show, Mock())
        tray._image_notifications._activate()
        page.pubsub.send_all.assert_called_once_with({"type": "window", "action": "show"})
        tray._image_notifications.close()
        tray._image_notifications._activate()
        self.assertEqual(page.pubsub.send_all.call_count, 1)

    def test_windows_click_legacy_and_version_four_focus_but_other_events_delegate(self):
        if sys.platform != "win32":
            self.skipTest("Windows backend binding")
        from pystray._util import win32
        activate = Mock()
        original = Mock(return_value=42)
        icon = SimpleNamespace(_message_handlers={win32.WM_NOTIFY: original})
        service = ImageNotifications(on_activate=activate)
        service.bind(icon)
        handler = icon._message_handlers[win32.WM_NOTIFY]
        service.bind(icon)
        self.assertIs(icon._message_handlers[win32.WM_NOTIFY], handler)
        for event in (0x402, 0x403, 0x404, 0x201, 0x202, 0x205):
            self.assertEqual(handler(123, event), 42)
        activate.assert_not_called()
        self.assertEqual(handler(123, 0x405), 0)
        self.assertEqual(handler(123, (99 << 16) | 0x405), 0)
        self.assertEqual(activate.call_count, 2)
        self.assertEqual(original.call_count, 6)
        service.close()
        self.assertIs(icon._message_handlers[win32.WM_NOTIFY], original)
        handler(123, 0x405)
        self.assertEqual(activate.call_count, 2)

    def test_windows_cleanup_does_not_overwrite_a_later_handler(self):
        if sys.platform != "win32":
            self.skipTest("Windows backend binding")
        from pystray._util import win32
        icon = SimpleNamespace(_message_handlers={win32.WM_NOTIFY: Mock()})
        service = ImageNotifications(on_activate=Mock())
        service.bind(icon)
        replacement = Mock()
        icon._message_handlers[win32.WM_NOTIFY] = replacement
        service.close()
        self.assertIs(icon._message_handlers[win32.WM_NOTIFY], replacement)

    def test_linux_default_action_is_localized_and_quiet_for_text_and_images(self):
        from utils.i18n import set_language
        self.addCleanup(set_language, "en")
        set_language("tr")
        glib = Mock()
        glib.Variant.side_effect = lambda signature, value: SimpleNamespace(signature=signature, value=value)
        gio = SimpleNamespace(DBusCallFlags=SimpleNamespace(NONE=0))
        notifier = SimpleNamespace(notify=Mock(), _notify=Mock(), _nid=0)
        proxy = notifier._notify
        proxy.connect.return_value = 5
        proxy.call_sync.return_value.unpack.return_value = (12,)
        activate = Mock()
        service = ImageNotifications(on_activate=activate)
        icon = SimpleNamespace(_notifier=notifier)
        modules = {"gi": Mock(), "gi.repository": SimpleNamespace(GLib=glib, Gio=gio)}
        with patch.dict(sys.modules, modules), patch("utils.image_notifications.sys.platform", "linux"):
            for path in (None, Path(tempfile.gettempdir()) / "earbuds.png"):
                proxy.call_sync.reset_mock()
                fallback = Mock()
                self.assertTrue(service._linux(icon, "body", "title", path, fallback, silent=True))
                self.assertFalse(glib.idle_add.call_args.args[0]())
                proxy.call_sync.assert_called_once()
                fallback.assert_not_called()
                payload = proxy.call_sync.call_args.args[1].value
                self.assertEqual(payload[2], path.as_uri() if path else "")
                self.assertEqual(payload[5], ["default", "Aç"])
                self.assertTrue(payload[6]["suppress-sound"].value)
            proxy.connect.assert_called_once_with("g-signal", service._linux_signal)
            signal = proxy.connect.call_args.args[1]
            for nid, key in ((999, "default"), (12, "other")):
                signal(proxy, "server", "ActionInvoked", SimpleNamespace(unpack=lambda: (nid, key)))
            activate.assert_not_called()
            signal(proxy, "server", "ActionInvoked", SimpleNamespace(unpack=lambda: (12, "default")))
            activate.assert_called_once_with()
            signal(proxy, "server", "ActionInvoked", SimpleNamespace(unpack=lambda: (12, "default")))
            activate.assert_called_once_with()
            service.close()
            proxy.disconnect.assert_called_once_with(5)

    def test_linux_dismissal_and_shutdown_never_activate_the_window(self):
        activate = Mock()
        proxy = Mock()
        service = ImageNotifications(on_activate=activate)
        service._bind_linux(SimpleNamespace(_notify=proxy))
        service._linux_ids.update((12, 13))
        args = SimpleNamespace(unpack=lambda: (12, 2))
        service._linux_signal(proxy, "server", "NotificationClosed", args)
        service._linux_signal(proxy, "server", "ActionInvoked", SimpleNamespace(unpack=lambda: (12, "default")))
        service._linux_signal(Mock(), "server", "ActionInvoked", SimpleNamespace(unpack=lambda: (13, "default")))
        service.close()
        service._linux_signal(proxy, "server", "ActionInvoked", SimpleNamespace(unpack=lambda: (13, "default")))
        activate.assert_not_called()

    def test_activation_callback_failure_is_contained(self):
        service = ImageNotifications(on_activate=Mock(side_effect=RuntimeError("closed page")))
        service._activate()
        service.close()
