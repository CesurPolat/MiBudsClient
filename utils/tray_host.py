"""Observe real Linux tray hosting, rather than just a visible flag."""
import re
import subprocess
import threading


class TrayHostMonitor:
    def __init__(self, icon, on_state):
        self.icon = icon
        self._callback = on_state
        self._stopped = threading.Event()
        self._gtk_pending = threading.Event()
        self._last = None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stopped.set()

    def _report(self, available):
        if not self._stopped.is_set() and available != self._last:
            self._last = available
            try:
                self._callback(available)
            except Exception as error:
                print(f"Tray host state update unavailable: {error}")

    @staticmethod
    def _indicator_host():
        for namespace in ("org.kde", "org.freedesktop"):
            try:
                result = subprocess.run([
                    "gdbus", "call", "--session", "--dest", namespace + ".StatusNotifierWatcher",
                    "--object-path", "/StatusNotifierWatcher", "--method",
                    "org.freedesktop.DBus.Properties.Get", namespace + ".StatusNotifierWatcher",
                    "IsStatusNotifierHostRegistered", "--timeout", "1",
                ], capture_output=True, text=True, check=False, timeout=1.5)
                if result.returncode == 0 and re.fullmatch(r"\(\s*<true>\s*,?\s*\)", result.stdout.strip()):
                    return True
            except (OSError, subprocess.SubprocessError):
                continue
        return False

    def _gtk_probe(self):
        self._gtk_pending.clear()
        if self._stopped.is_set():
            return False
        try:
            self._report(bool(self.icon._status_icon.is_embedded()))
        except Exception:
            self._report(False)
        return False

    def _run(self):
        while not self._stopped.is_set():
            try:
                backend = type(self.icon).__module__
                if backend == "pystray._appindicator":
                    self._report(self._indicator_host())
                elif backend == "pystray._gtk":
                    from gi.repository import GLib
                    # GTK objects belong to the native tray loop, not this worker.
                    if not self._gtk_pending.is_set():
                        self._gtk_pending.set()
                        GLib.idle_add(self._gtk_probe)
                elif backend == "pystray._xorg":
                    self._report(getattr(self.icon, "_systray_manager", None) is not None)
            except Exception:
                self._report(False)
            if self._stopped.wait(2):
                return
