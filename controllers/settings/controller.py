"""Bind settings controls to startup, device, and latency actions."""

import threading
from typing import Callable

from utils.startup_manager import is_startup_enabled, set_startup
from ui.components.settings_card import SettingsCard
from .gestures import GestureSettingsController


class SettingsController:
    """Build the settings controls and handle their application callbacks."""

    def __init__(self, *, controller, latency, device_connection,
                 publish: Callable[[dict], None], on_update: Callable[[], None]):
        self._controller = controller
        self._device_connection = device_connection
        self._publish = publish
        self._on_update = on_update
        self.card = SettingsCard(
            on_gesture_refresh=lambda: self.gestures.refresh(),
            on_gesture_assignment=lambda *args: self.gestures.assign(*args),
            on_update=on_update,
            on_check_device_identity=self.on_check_device_identity,
            on_low_latency_mode_change=latency.on_latency_mode_change,
            on_add_low_latency_list_item=latency.on_add_low_latency_list_item,
            on_remove_low_latency_list_item=latency.on_remove_low_latency_list_item,
            on_set_low_latency_item_mode=latency.on_set_low_latency_item_mode,
            on_add_low_latency_include_item=latency.on_add_low_latency_include_item,
            on_wait_until_app_close_change=latency.on_wait_until_app_close_change,
            on_check_battery=lambda _: controller.request_battery(),
            on_startup_toggle=self.on_startup_change,
            startup_enabled=is_startup_enabled(),
            low_latency_mode=latency.state["selected_mode"],
            active_platform=latency.platform_key,
            low_latency_exclusions_by_platform={
                "windows": sorted(latency.low_latency_exceptions_by_platform.get("windows", [])),
                "linux": sorted(latency.low_latency_exceptions_by_platform.get("linux", [])),
            },
            low_latency_inclusions_by_platform={
                "windows": sorted(latency.low_latency_includes_by_platform.get("windows", [])),
                "linux": sorted(latency.low_latency_includes_by_platform.get("linux", [])),
            },
            wait_until_app_close_enabled=latency.state["hold_until_app_close_enabled"],
        )
        self.gestures = GestureSettingsController(controller, self.card.gestures, publish)

    def on_startup_change(self, e):
        enabled = e.control.value
        if set_startup(enabled):
            self._device_connection.update_status(
                f"Startup {'enabled' if enabled else 'disabled'}",
                "green" if enabled else "white"
            )
        else:
            self._device_connection.update_status("Failed to change startup setting", "red")
            e.control.value = not enabled
            self._on_update()

    def on_check_device_identity(self, e):
        if self.card.identity_item.disabled:
            return
        self.card.set_device_identity_result("Reading device identity...", pending=True)
        self._on_update()

        def query_identity():
            try:
                success, message = self._controller.request_device_identity()
            except Exception as exc:
                success, message = False, f"Device identity request failed: {exc}"
            self._publish({"type": "device_identity", "text": message})
            self._device_connection.update_status(message, "green" if success else "red")

        threading.Thread(target=query_identity, daemon=True).start()
