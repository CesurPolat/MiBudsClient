"""Route application pubsub messages to controllers and UI components."""

from utils.i18n import t

import time
import threading
from typing import Callable

from .constants import BATTERY_UNKNOWN
from .components.update_notification import show_update_notification
from .localization import refresh_translations
from .battery_notifications import BatteryNotificationState
from utils.i18n import LANGUAGE_CHOICES, is_rtl, set_language
from utils.user_preferences import set_language_preference
from utils.sound import play_connection_melody


class AppMessageHandler:
    """Handle incoming messages while keeping application startup in main."""

    def __init__(self, *, page, device_status_card, settings_card, window_manager,
                 latency, tray, debug_console, on_window_show: Callable,
                 get_game_monitor: Callable, on_catalog_stop: Callable | None = None, get_capabilities: Callable | None = None,
                 ui_lock=None):
        self._dispatch_lock = ui_lock if ui_lock is not None else threading.RLock()
        self._closing = False
        self._get_capabilities = get_capabilities
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
        self._connection_melody_played = False
        self._battery_notifications = BatteryNotificationState()
        self._notification_lock = threading.RLock()
        self._connection_notification_timer = None
        self._connection_notification_token = 0
        self._connection_notification_pending = False
        self._last_debug_toggle_at = 0.0
        self._routes = {
            "capabilities_changed": self._handle_capabilities_changed,
            "language": self._handle_language,
            "gesture_settings": self._handle_gesture_settings,
            "eq_settings": self._handle_eq_settings,
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
            "connection_notification_timeout": self._handle_connection_notification_timeout,
            "fullscreen_state": self._handle_fullscreen_state,
        }

    def _handle_capabilities_changed(self, message):
        if self._get_capabilities is not None:
            capabilities = self._get_capabilities()
            self._settings_card.set_capabilities(capabilities)
            self._latency.set_device_capabilities(capabilities)
            self._tray.refresh_menu()
        self._update_page()

    def _handle_language(self, message: dict) -> None:
        language = message.get("language")
        if not isinstance(language, str) or language not in LANGUAGE_CHOICES:
            return
        set_language_preference(language)
        set_language(language)
        self._page.rtl = is_rtl()
        self._settings_card.language_selector.value = language
        self._tray.refresh_menu()
        self._update_page()

    def _update_page(self) -> None:
        refresh_translations(self._page.controls)
        refresh_translations(self._page.overlay)
        self._page.update()

    def handle(self, message) -> None:
        """Ignore unrelated messages and dispatch recognized message types."""
        # Pubsub delivers synchronous callbacks on concurrent executor threads.
        # Flet control-list diffs must be generated and sent in the same order.
        with self._dispatch_lock:
            self._handle_message(message)

    def _handle_message(self, message) -> None:
        if self._closing:
            return
        if not isinstance(message, dict):
            return
        callback = getattr(self, "report_message", None)
        if callback and callback(message):
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
        self._update_page()

    def _handle_connection_state(self, message: dict) -> None:
        if self._get_capabilities is not None:
            capabilities = self._get_capabilities()
            self._settings_card.set_capabilities(capabilities)
            self._latency.set_device_capabilities(capabilities)
            self._tray.refresh_menu()
        if message.get("state") in {"connecting", "failed"}:
            with self._notification_lock:
                # Preserve the last sample for the disconnect description, but
                # do not accept late battery updates after a connection failure.
                self._battery_notifications.active = False
        self._settings_card.update_connection_state(
            message.get("state", ""), message.get("reason", "")
        )
        self._update_page()

    def _handle_catalog_device(self, message: dict) -> None:
        self._tray.set_device(message.get("name", ""), message.get("image_path", ""))
        self._device_status_card.update_catalog_device(
            message.get("name", ""), message.get("image_path", "")
        )
        self._update_page()

    def _handle_battery(self, message: dict) -> None:
        left = message.get("left", BATTERY_UNKNOWN)
        right = message.get("right", BATTERY_UNKNOWN)
        case = message.get("case", BATTERY_UNKNOWN)
        transient = message.get("transient", False)

        if not transient:
            with self._notification_lock:
                removed = self._battery_notifications.update(left, right, case)
                inserted = self._battery_notifications.inserted
                if (self._connection_notification_pending and self._battery_notifications.active
                        and self._battery_notifications.has_earbud_data):
                    self._cancel_connection_notification()
                    self._tray.notify(self._battery_notifications.body(t("tray.connected")), device=True, silent=True)
                elif removed or inserted:
                    def event(kind, sides):
                        key = "both" if len(sides) == 2 else sides[0]
                        return t("notification." + kind + "_" + key)

                    if removed and inserted:
                        text = t("notification.case_changes", removed=event("removed", removed),
                                 inserted=event("inserted", inserted))
                    else:
                        text = event("removed", removed) if removed else event("inserted", inserted)
                    self._tray.notify(self._battery_notifications.body(text), device=True, silent=True)

        self._device_status_card.update_battery(left, right, case, transient=transient)

        self._update_page()

    def _handle_device_identity(self, message: dict) -> None:
        self._settings_card.set_device_identity_result(message["text"])
        self._update_page()

    def _handle_gesture_settings(self, message: dict) -> None:
        self._settings_card.gestures.complete(
            message["token"], message["result"], message["capabilities"]
        )
        self._update_page()

    def _handle_eq_settings(self, message: dict) -> None:
        self._settings_card.equalizer.complete(
            message["token"], message["result"], message["profiles"], message["operation"]
        )
        self._update_page()

    def _handle_window(self, message: dict) -> None:
        action = message.get("action")
        if action == "show":
            self._window_manager.apply_show()
            self._on_window_show()
            callback = getattr(self, "report_on_show", None)
            if callback:
                callback()
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
                text, color = t("latency.automatic_set"), "blue" if enabled else "white"
            elif mode == "on":
                text, color = t("latency.low_set"), "blue"
            else:
                text, color = t("latency.standard_set"), "white"
            self._publish_status(text, color)
            self._update_page()

    def _handle_auto_hold_released(self, message: dict) -> None:
        self._latency.on_hold_released(str(message.get("app_id", "")))

    def _handle_update_notification(self, message: dict) -> None:
        show_update_notification(self._page, message.get("latest_ver"))

    def _handle_app(self, message: dict) -> None:
        if message.get("action") != "close":
            return
        self._closing = True
        with self._notification_lock:
            self._cancel_connection_notification()
            self._battery_notifications.reset()
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
            self._device_status_card.update_status(t("debug.opened"), "blue")
        elif result == "closed":
            self._device_status_card.update_status(t("debug.closed"), "white")
        else:
            self._device_status_card.update_status(t("debug.failed"), "red")
        self._update_page()

    def _handle_connection_event(self, message: dict) -> None:
        event = message.get("event")
        if event not in ("connected", "disconnected"):
            return
        with self._notification_lock:
            if event == self._last_connection_event:
                return
            self._last_connection_event = event
            self._cancel_connection_notification()
            if event == "connected":
                if not self._connection_melody_played:
                    self._connection_melody_played = True
                    play_connection_melody()
                self._battery_notifications.reset(active=True)
                self._connection_notification_pending = True
                token = self._connection_notification_token
                timer = threading.Timer(3.0, lambda: self._page.pubsub.send_all(
                    {"type": "connection_notification_timeout", "token": token}
                ))
                timer.daemon = True
                self._connection_notification_timer = timer
                timer.start()
            else:
                self._latency.clear_latency_hold()
                self._tray.notify(self._battery_notifications.body(t("tray.disconnected"), last_known=True), device=True, silent=True)
                self._battery_notifications.reset()

    def _cancel_connection_notification(self):
        self._connection_notification_token += 1
        self._connection_notification_pending = False
        if self._connection_notification_timer is not None:
            self._connection_notification_timer.cancel()
            self._connection_notification_timer = None

    def _handle_connection_notification_timeout(self, message):
        with self._notification_lock:
            if (message.get("token") != self._connection_notification_token
                    or not self._connection_notification_pending
                    or not self._battery_notifications.active):
                return
            self._cancel_connection_notification()
            self._tray.notify(self._battery_notifications.body(t("tray.connected")), device=True, silent=True)

    def _handle_fullscreen_state(self, message: dict) -> None:
        is_fullscreen = bool(message.get("is_fullscreen", False))
        app_id = str(message.get("app_id", "")).strip().lower()
        self._latency.on_monitor_state(is_fullscreen, app_id)
