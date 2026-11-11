"""Desktop notifications independent of GTK widgets and pystray internals."""

import html
from pathlib import Path
import queue
import threading

from .resource_manager import get_resource_path
from .tray_backend import _ensure_gi_module

SERVICE = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"


class LinuxNotifications:
    def __init__(self, on_activate=None):
        self._activate = on_activate
        self._lock = threading.RLock()
        self._stopped = threading.Event()
        self._pending = queue.Queue(maxsize=32)
        self._thread = None
        self._loop = None
        self._ids = set()

    def notify(self, message, title, image_path="", *, silent=True, action_label="Open"):
        with self._lock:
            if self._stopped.is_set():
                return False
            try:
                self._pending.put_nowait((message, title, image_path, silent, action_label))
            except queue.Full:
                print("Desktop notification queue is full")
                return False
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()
            return True

    def _call(self, method, parameters=None):
        return self._connection.call_sync(
            SERVICE, PATH, SERVICE, method, parameters, None,
            self._Gio.DBusCallFlags.NO_AUTO_START, 2000, None,
        ).unpack()

    def _deliver(self, message, title, image_path, silent, action_label):
        # Read capabilities again so a restarted/replaced notification daemon
        # cannot leave stale assumptions about clickable actions or markup.
        capabilities = self._call("GetCapabilities")[0]
        actions = ["default", action_label] if "actions" in capabilities and self._activate else []
        icon = ""
        if image_path:
            try:
                path = Path(get_resource_path(image_path)).resolve(strict=True)
                if path.is_file():
                    icon = path.as_uri()
            except OSError:
                pass  # A stale image must not suppress the text notification.
        body = html.escape(message, quote=False) if "body-markup" in capabilities else message
        hints = {"suppress-sound": self._GLib.Variant("b", True)} if silent else {}
        parameters = self._GLib.Variant("(susssasa{sv}i)", (
            "MiBudsClient", 0, icon, title, body, actions, hints, -1,
        ))
        try:
            notification_id = self._call("Notify", parameters)[0]
        except Exception:
            if not icon:
                raise
            # Some servers reject an image URI. Retry once with text and keep
            # the same actions and sound hint; never fall back to a noisy API.
            notification_id = self._call("Notify", self._GLib.Variant("(susssasa{sv}i)", (
                "MiBudsClient", 0, "", title, body, actions, hints, -1,
            )))[0]
        if actions:
            if len(self._ids) >= 256:
                self._ids.clear()
            self._ids.add(notification_id)

    def _signal(self, connection, sender, path, interface, name, parameters):
        try:
            notification_id, value = parameters.unpack()
            if self._stopped.is_set() or notification_id not in self._ids:
                return
            if name == "NotificationClosed":
                self._ids.discard(notification_id)
            elif name == "ActionInvoked" and value == "default":
                self._ids.discard(notification_id)
                if self._activate:
                    self._activate()
        except Exception as error:
            print(f"Notification activation unavailable: {error}")

    def _drain(self, *_):
        if self._stopped.is_set():
            if self._loop is not None:
                self._loop.quit()
            return False
        # Limit each batch so action signals are not starved by a log burst.
        for _ in range(1):
            try:
                item = self._pending.get_nowait()
            except queue.Empty:
                break
            if self._stopped.is_set():
                if self._loop is not None:
                    self._loop.quit()
                return False
            try:
                self._deliver(*item)
            except Exception as error:
                print(f"Desktop notification unavailable: {error}")
        return True

    def _run(self):
        source = context = None
        subscriptions = []
        try:
            if not _ensure_gi_module():
                raise ImportError("PyGObject with Gio/GLib is required for Linux notifications")
            from gi.repository import Gio, GLib
            self._Gio, self._GLib = Gio, GLib
            context = GLib.MainContext.new()
            context.push_thread_default()
            self._connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            for name in ("ActionInvoked", "NotificationClosed"):
                subscriptions.append(self._connection.signal_subscribe(
                    SERVICE, SERVICE, name, PATH, None, Gio.DBusSignalFlags.NONE, self._signal,
                ))
            subscriptions.append(self._connection.signal_subscribe(
                "org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
                "/org/freedesktop/DBus", SERVICE, Gio.DBusSignalFlags.NONE,
                lambda *_: self._ids.clear(),
            ))
            source = GLib.timeout_source_new(100)
            source.set_callback(self._drain)
            source.attach(context)
            with self._lock:
                if self._stopped.is_set():
                    return
                self._loop = GLib.MainLoop.new(context, False)
            # Run even if close() raced this point: the periodic source wakes
            # the context and quits it as soon as shutdown is observed.
            if not self._stopped.is_set():
                self._loop.run()
        except Exception as error:
            print(f"Linux notifications unavailable: {error}")
            while True:
                try:
                    self._pending.get_nowait()
                except queue.Empty:
                    break
        finally:
            if source is not None:
                source.destroy()
            for subscription in subscriptions:
                self._connection.signal_unsubscribe(subscription)
            if context is not None:
                context.pop_thread_default()
            with self._lock:
                self._loop = None
                self._ids.clear()

    def close(self):
        with self._lock:
            self._stopped.set()
            if self._loop is not None:
                self._loop.quit()
