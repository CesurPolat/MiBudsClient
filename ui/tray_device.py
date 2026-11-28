"""Handle tray device actions and publish device snapshots from the UI loop."""

import threading

from controllers.battery.stream import BATTERY_UNKNOWN


class TrayDeviceEvents:
    def __init__(self, *, tray, settings, latency, get_capabilities, get_session,
                 is_connected, set_single_body):
        self._tray = tray
        self._settings = settings
        self._latency = latency
        self._get_capabilities = get_capabilities
        self._get_session = get_session
        self._is_connected = is_connected
        self._set_single_body = set_single_body
        self._session = None
        self._battery = (BATTERY_UNKNOWN,) * 3

    def routes(self):
        return {"tray_device_action": self.on_action}

    def sync(self):
        if self._get_capabilities is None or self._get_session is None or self._is_connected is None:
            return
        session = self._get_session()
        connected = self._is_connected()
        if session != self._session or not connected:
            self._battery = (BATTERY_UNKNOWN,) * 3
        self._session = session
        capabilities = self._get_capabilities()
        self._set_single_body(capabilities.single_body)
        self._tray.set_state({
            "session": session, "connected": connected, "name": capabilities.name,
            "battery": self._battery,
            "single_body": capabilities.single_body,
            "eq": self._settings.equalizer.tray_state(capabilities),
            "noise": self._settings.noise.tray_state(),
            "latency": self._latency.get_display_state(),
            "latency_available": capabilities.supports("latency"),
        })

    def on_battery(self, left, right, case, *, transient):
        # A UI-only battery refresh must not overwrite the last device sample.
        if not transient and self._is_connected is not None and self._is_connected():
            self._battery = (left, right, case)

    def on_action(self, message):
        if (self._get_capabilities is None or self._get_session is None or self._is_connected is None
                or not self._is_connected() or message.get("session") != self._get_session()):
            return
        capabilities = self._get_capabilities()
        feature = message.get("feature")
        operation = message.get("operation")
        if feature == "eq" and capabilities.supports("eq"):
            profile = message.get("profile")
            if operation == "read" or (type(profile) is int and profile in capabilities.profiles and profile != 10):
                self._settings.equalizer.select_from_tray(operation, profile)
        elif feature == "noise" and capabilities.supports("noise"):
            self._settings.noise.select_from_tray(operation, message.get("mode"), message.get("level"))
        elif feature == "latency" and operation == "toggle" and capabilities.supports("latency"):
            threading.Thread(target=self._latency.toggle_latency_from_tray,
                             args=(message["session"],), daemon=True).start()
        self.sync()
