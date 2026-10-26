"""Coordinate device callbacks, battery requests, and reconnects for the UI."""

from utils.i18n import message as m

import threading
import time
from typing import Callable

from .battery_updates import BatteryUpdates


class DeviceConnection:
    """Publish device updates and run connection work outside UI callbacks."""

    def __init__(self, publish: Callable[[dict], None], get_controller: Callable):
        self._publish = publish
        self._get_controller = get_controller
        self._battery_updates = BatteryUpdates(publish)
        self._reconnect_lock = threading.Lock()
        self._reconnect_in_progress = False

    def update_status(self, text: str, color: str = "white") -> None:
        self._publish({"type": "status", "text": text, "color": color})

    def update_battery(self, left: int, right: int, case: int) -> None:
        self._battery_updates.update(left, right, case)

    def request_battery_delayed(self) -> None:
        """Request battery data after the existing one-second startup delay."""
        threading.Thread(target=self._request_battery_delayed, daemon=True).start()

    def _request_battery_delayed(self) -> None:
        time.sleep(1)
        controller = self._get_controller()
        if controller is not None:
            controller.resume_reconnect_attempts()
            controller.request_battery()

    def reconnect_on_show(self) -> None:
        """Reconnect when the window is shown, allowing only one worker at a time."""
        controller = self._get_controller()
        if controller is None or controller.connected:
            return
        with self._reconnect_lock:
            if self._reconnect_in_progress:
                return
            self._reconnect_in_progress = True

        def reconnect_worker() -> None:
            try:
                controller.resume_reconnect_attempts()
                self.update_status(m("connection.reconnecting"), "orange")
                controller.reconnect(force_rediscovery=True)
            finally:
                self._reset_reconnect()

        try:
            threading.Thread(target=reconnect_worker, daemon=True).start()
        except Exception:
            self._reset_reconnect()
            raise

    def _reset_reconnect(self) -> None:
        with self._reconnect_lock:
            self._reconnect_in_progress = False
