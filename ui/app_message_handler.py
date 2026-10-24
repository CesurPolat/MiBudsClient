"""Route application pubsub messages to controllers and UI components."""

import time
import threading
from typing import Callable

from .constants import BATTERY_UNKNOWN
from .components.update_notification import show_update_notification


class AppMessageHandler:
    """Handle incoming messages while keeping application startup in main."""

    def __init__(self, *, page, device_status_card, settings_card, window_manager,
                 latency, tray, debug_console, on_window_show: Callable,
                 get_game_monitor: Callable, on_catalog_stop: Callable | None = None):
        self._page = page
        self._device_status_card = device_status_card
        self._settings_card = settings_card
        self._window_manager = window_manager
        self._latency = latency
        self._latency_display_lock = threading.Lock()
        self._tray = tray
        self._debug_console = debug_console
        self._on_window_show = on_window_show
        self._get_game_monitor = get_game_monitor
        self._on_catalog_stop = on_catalog_stop
        self._last_connection_event = None
        self._last_debug_toggle_at = 0.0
        self._routes = {
            "catalog_device": self._handle_catalog_device,
            "connection_state": self._handle_connection_state,
            "status": self._handle_status,
            "battery": self._handle_battery,
            "device_identity": self._handle_device_identity,
            "window": self._handle_window,
            "latency": self._handle_latency,
            "auto_hold_released": self._handle_auto_hold_released,
            "update_notification": self._handle_update_notification,
            "app": self._handle_app,
            "debug_console": self._handle_debug_console,
            "connection_event": self._handle_connection_event,
            "fullscreen_state": self._handle_fullscreen_state,
        }

    def handle(self, message) -> None:
        """Ignore unrelated messages and dispatch recognized message types."""
        if not isinstance(message, dict):
            return
        message_type = message.get("type")
        if not isinstance(message_type, str):
            return
        handler = self._routes.get(message_type)
        if handler:
            handler(message)

    def _publish_status(self, text: str, color: str = "white") -> None:
        self._page.pubsub.send_all({"type": "status", "text": text, "color": color})

    def _handle_status(self, message: dict) -> None:
        self._device_status_card.update_status(
            message.get("text", ""),
            message.get("color", "white")
        )
        self._page.update()

    def _handle_connection_state(self, message: dict) -> None:
        self._settings_card.update_connection_state(
            message.get("state", ""), message.get("reason", "")
        )
        self._page.update()

    def _handle_catalog_device(self, message: dict) -> None:
        self._device_status_card.update_catalog_device(
            message.get("name", ""), message.get("image_path", "")
        )
        self._page.update()

    def _handle_battery(self, message: dict) -> None:
        left = message.get("left", BATTERY_UNKNOWN)
        right = message.get("right", BATTERY_UNKNOWN)
        case = message.get("case", BATTERY_UNKNOWN)
        transient = message.get("transient", False)

        self._device_status_card.update_battery(left, right, case, transient=transient)

        self._page.update()

    def _handle_device_identity(self, message: dict) -> None:
        self._settings_card.set_device_identity_result(message["text"])
        self._page.update()

    def _handle_window(self, message: dict) -> None:
        action = message.get("action")
        if action == "show":
            self._window_manager.apply_show()
            self._on_window_show()
        elif action == "hide":
            self._window_manager.apply_hide()

    def _handle_latency(self, message: dict) -> None:
        # Notifications can be delayed or reordered. Always render current state.
        with self._latency_display_lock:
            state = self._latency.get_display_state()
            mode, enabled = state["mode"], state["enabled"]
            self._settings_card.set_latency_mode(mode)
            if state["error"]:
                text, color = state["error"], "red"
            elif mode == "auto":
                text, color = "Automatic mode set", "blue" if enabled else "white"
            elif mode == "on":
                text, color = "Low Latency mode set", "blue"
            else:
                text, color = "Standard mode set", "white"
            self._publish_status(text, color)
            self._page.update()

    def _handle_auto_hold_released(self, message: dict) -> None:
        self._latency.on_hold_released(str(message.get("app_id", "")))

    def _handle_update_notification(self, message: dict) -> None:
        show_update_notification(self._page, message.get("latest_ver"))

    def _handle_app(self, message: dict) -> None:
        if message.get("action") != "close":
            return
        if self._on_catalog_stop:
            self._on_catalog_stop()
        game_monitor = self._get_game_monitor()
        if game_monitor:
            game_monitor.stop()
        self._debug_console.stop_f12_hotkey_listener()
        self._window_manager.close()

    def _handle_debug_console(self, message: dict) -> None:
        action = message.get("action")
        if action != "toggle":
            return

        now = time.monotonic()
        if now - self._last_debug_toggle_at < 0.35:
            return
        self._last_debug_toggle_at = now

        result = self._debug_console.toggle_console()
        if result == "opened":
            self._device_status_card.update_status("Debug console opened", "blue")
        elif result == "closed":
            self._device_status_card.update_status("Debug console closed", "white")
        else:
            self._device_status_card.update_status("Debug console could not be opened", "red")
        self._page.update()

    def _handle_connection_event(self, message: dict) -> None:
        event = message.get("event")
        if event == self._last_connection_event:
            return

        self._last_connection_event = event
        if event == "connected":
            self._tray.notify("Earbuds connected")
        elif event == "disconnected":
            self._latency.clear_latency_hold()
            self._tray.notify("Earbuds disconnected")

    def _handle_fullscreen_state(self, message: dict) -> None:
        is_fullscreen = bool(message.get("is_fullscreen", False))
        app_id = str(message.get("app_id", "")).strip().lower()
        self._latency.on_monitor_state(is_fullscreen, app_id)
