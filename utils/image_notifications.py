"""Small image adapters for the existing pystray Windows and Linux backends.

No downloads, shell commands, or replacement UI framework. Private pystray
integration stays here so unsupported/changed backends can fall back to text.
"""

import sys
import threading
from pathlib import Path

from PIL import Image, ImageOps

from .resource_manager import get_resource_path
from .i18n import t


class ImageNotifications:
    def __init__(self, on_activate=None):
        self._handles = {}
        self._lock = threading.RLock()
        self._closed = False
        self._on_activate = on_activate
        self._windows_binding = None
        self._linux_binding = None
        self._linux_ids = set()

    def _activate(self):
        with self._lock:
            callback = self._on_activate if not self._closed else None
        if callback is not None:
            try:
                # The app supplies WindowManager.show, which publishes to Flet
                # rather than changing page controls on a native callback thread.
                callback()
            except Exception as exc:
                print(f"Notification activation failed: {exc}")

    def bind(self, icon):
        """Add the Windows balloon-click handler without changing tray actions."""
        if sys.platform != "win32" or self._on_activate is None:
            return
        from pystray._util import win32
        with self._lock:
            if self._closed or self._windows_binding is not None:
                return
            handlers = getattr(icon, "_message_handlers", None)
            if not isinstance(handlers, dict):
                return
            original = handlers.get(win32.WM_NOTIFY)
            if not callable(original):
                return

            def notify(wparam, lparam):
                if (lparam & 0xFFFF) == 0x405:  # NIN_BALLOONUSERCLICK; also accept version-4 layout
                    self._activate()
                    return 0
                return original(wparam, lparam)

            handlers[win32.WM_NOTIFY] = notify
            self._windows_binding = (handlers, win32.WM_NOTIFY, original, notify)

    def _bind_linux(self, notifier):
        """Listen only for actions belonging to notifications sent by this service."""
        if self._on_activate is None:
            return False
        proxy = notifier._notify
        if self._linux_binding is not None:
            return self._linux_binding[0] is proxy
        signal_id = proxy.connect("g-signal", self._linux_signal)
        self._linux_binding = (proxy, signal_id)
        return True

    def _linux_signal(self, proxy, sender_name, signal_name, parameters):
        try:
            notification_id, value = parameters.unpack()
            with self._lock:
                if (self._closed or self._linux_binding is None or self._linux_binding[0] is not proxy
                        or notification_id not in self._linux_ids):
                    return
                if signal_name == "NotificationClosed":
                    self._linux_ids.discard(notification_id)
                    return
                if signal_name != "ActionInvoked" or value != "default":
                    return
                self._linux_ids.discard(notification_id)
            self._activate()
        except Exception as exc:
            print(f"Notification action unavailable: {exc}")

    def show(self, icon, message: str, title: str, image_path: str, fallback, *, silent=False) -> bool:
        """Return whether an image notification was sent or scheduled.

        Linux delivers on its existing GLib loop; delivery errors there call the
        supplied text fallback. Windows native icon handles live until tray exit.
        """
        try:
            self.bind(icon)
            path = Path(get_resource_path(image_path)).resolve(strict=True) if image_path else None
            if self._closed or (path is not None and not path.is_file()) or (path is None and not silent):
                return False
            if sys.platform == "win32":
                return self._windows(icon, message, title, path, silent=silent)
            if sys.platform.startswith("linux"):
                if path is not None:
                    with Image.open(path) as image:
                        image.verify()
                return self._linux(icon, message, title, path, fallback, silent=silent)
        except Exception as exc:
            print(f"Image notification unavailable: {exc}")
        return False

    def _windows(self, icon, message, title, path, *, silent=False):
        if not getattr(icon, "_hwnd", None) or not callable(getattr(icon, "_message", None)):
            return False
        import ctypes
        from pystray._util import serialized_image, win32

        with self._lock:
            if self._closed:
                return False
            handle = self._icon_handle(path, ctypes, serialized_image, win32) if path is not None else None
            if path is not None and not handle:
                return False

            def limit(text, units):
                return text.replace("\0", "").encode("utf-16-le")[:units * 2].decode("utf-16-le", errors="ignore")

            icon._message(
                win32.NIM_MODIFY, win32.NIF_INFO,
                szInfo=limit(message, 255), szInfoTitle=limit(title, 63),
                dwInfoFlags=(0x24 if handle else 0) | (0x10 if silent else 0),
                # NIIF_USER | NIIF_LARGE_ICON, optionally NIIF_NOSOUND.
                hBalloonIcon=handle,
            )
            return True

    def _icon_handle(self, path, ctypes, serialized_image, win32):
            size = (ctypes.windll.user32.GetSystemMetrics(11),
                    ctypes.windll.user32.GetSystemMetrics(12))  # SM_CXICON / SM_CYICON
            if min(size) <= 0:
                return None
            info = path.stat()
            key = (str(path), info.st_mtime_ns, info.st_size, size)
            handle = self._handles.get(key)
            if handle is None:
                with Image.open(path) as source:
                    thumbnail = ImageOps.contain(source.convert("RGBA"), size, Image.Resampling.LANCZOS)
                canvas = Image.new("RGBA", size)
                canvas.paste(thumbnail, ((size[0] - thumbnail.width) // 2,
                                         (size[1] - thumbnail.height) // 2))
                try:
                    with serialized_image(canvas, "ICO") as filename:
                        handle = win32.LoadImage(None, filename, win32.IMAGE_ICON,
                                                 *size, win32.LR_LOADFROMFILE)
                    if not handle:
                        return None
                    self._handles[key] = handle
                finally:
                    thumbnail.close()
                    canvas.close()

            return handle

    def _linux(self, icon, message, title, path, fallback, *, silent=False):
        notifier = getattr(icon, "_notifier", None)
        if notifier is None or not callable(getattr(notifier, "notify", None)):
            return False
        from gi.repository import GLib

        def deliver():
            with self._lock:
                if self._closed:
                    return False
                try:
                    # The pystray DBus notifier copies this cached image before
                    # publishing it, leaving the app's tray icon unchanged.
                    actions = []
                    if self._on_activate is not None:
                        try:
                            if self._bind_linux(notifier):
                                actions = ["default", t("tray.open")]
                        except Exception as exc:
                            print(f"Notification click support unavailable: {exc}")
                    if silent or actions:
                        from gi.repository import Gio
                        image = str(path.as_uri()) if path is not None else ""
                        notifier._nid = notifier._notify.call_sync(
                            "Notify", GLib.Variant("(susssasa{sv}i)", (
                                "Mi Buds Client", notifier._nid, image, title, message, actions,
                                {"suppress-sound": GLib.Variant("b", True)} if silent else {}, -1,
                            )), Gio.DBusCallFlags.NONE, 3000, None,
                        ).unpack()[0]
                        if actions:
                            self._linux_ids.add(notifier._nid)
                    else:
                        notifier.notify(title, message, str(path))
                except Exception as exc:
                    print(f"Image notification delivery failed: {exc}")
                    fallback()
            return False

        GLib.idle_add(deliver)
        return True

    def close(self):
        """Release HICONs only after the tray's native loop has stopped."""
        with self._lock:
            self._closed = True
            if self._windows_binding is not None:
                handlers, message, original, installed = self._windows_binding
                if handlers.get(message) is installed:
                    handlers[message] = original
                self._windows_binding = None
            if self._linux_binding is not None:
                proxy, signal_id = self._linux_binding
                try:
                    proxy.disconnect(signal_id)
                except Exception as exc:
                    print(f"Notification signal cleanup failed: {exc}")
                self._linux_binding = None
            self._linux_ids.clear()
            if self._handles:
                from pystray._util import win32
                for handle in self._handles.values():
                    win32.DestroyIcon(handle)
                self._handles.clear()
