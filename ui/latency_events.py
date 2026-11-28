"""Apply latency and game-monitor topics on the UI loop."""

import threading

from utils.app.i18n import t


class LatencyEvents:
    def __init__(self, *, latency, settings, publish, update_page):
        self._latency = latency
        self._settings = settings
        self._publish = publish
        self._update_page = update_page
        self._display_lock = threading.Lock()

    def routes(self):
        return {
            "latency": self.on_latency,
            "auto_hold_released": self.on_hold_released,
            "fullscreen_state": self.on_fullscreen_state,
        }

    def on_latency(self, message):
        self.refresh()

    def refresh(self):
        # Messages can arrive out of order. Render the controller's current state.
        with self._display_lock:
            state = self._latency.get_display_state()
            mode, enabled = state["mode"], state["enabled"]
            self._settings.set_latency_mode(mode)
            self._settings.latency_item.set_device_state(enabled, state.get("activation_app", ""))
            if state["error"]:
                text, color = state["error"], "red"
            elif enabled is None:
                text, color = t("latency.unknown"), "white"
            elif enabled:
                text, color = t("latency.low_set"), "blue"
            else:
                text, color = t("latency.standard_set"), "white"
            self._publish({"type": "status", "text": text, "color": color})
            self._update_page()

    def on_hold_released(self, message):
        self._latency.on_hold_released(str(message.get("app_id", "")))

    def on_fullscreen_state(self, message):
        is_fullscreen = bool(message.get("is_fullscreen", False))
        app_id = str(message.get("app_id", "")).strip().lower()
        self._latency.on_monitor_state(is_fullscreen, app_id)
