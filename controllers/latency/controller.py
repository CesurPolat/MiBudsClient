"""Coordinate device state, automatic policy and latency callbacks."""

import sys
import threading
from functools import wraps
from typing import Callable

from utils.app.i18n import message as m
from utils.app.pubsub_topics import PubSubTopic
from utils.app.user_preferences import (
    get_low_latency_hold_until_app_close,
    get_low_latency_mode,
    set_low_latency_hold_until_app_close,
    set_low_latency_mode,
)

from .device import LatencyDevice
from .hold import HoldWatcher, is_process_running
from .policy import evaluate_policy
from .rules import LatencyRules


def _serialized(method):
    """Serialize state changes originating from tray, UI, and monitor callbacks."""
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            if self._stopped.is_set():
                return
            return method(self, *args, **kwargs)
    return call


class LatencyController:
    """Coordinate mode changes through callbacks, independently of Flet controls."""

    def __init__(self, publish: Callable, get_controller: Callable,
                 get_tray: Callable, on_rules_change: Callable,
                 on_ui_update: Callable):
        self._lock = threading.RLock()
        self._stopped = threading.Event()
        self._publish = publish
        self._get_controller = get_controller
        self._get_tray = get_tray
        self._on_rules_change = on_rules_change
        self._on_ui_update = on_ui_update
        self.state = {
            "selected_mode": get_low_latency_mode(),
            "effective_low_latency": None,
            "latency_hold_app_id": "",
            "hold_watcher_running": False,
            "hold_until_app_close_enabled": get_low_latency_hold_until_app_close(),
            "last_monitor_state": {"is_fullscreen": False, "app_id": ""},
        }
        self.platform_key = "windows" if sys.platform.startswith("win") else "linux"
        self._rules = LatencyRules()
        self._device = LatencyDevice(get_controller, self._stopped, self.state)
        self._hold = HoldWatcher(
            state=self.state, lock=self._lock, stopped=self._stopped,
            check_process=lambda app_id: self.is_process_running(app_id), publish=publish,
        )

    @property
    def low_latency_exceptions_by_platform(self) -> dict[str, list[str]]:
        return self._rules.exceptions_by_platform

    @property
    def low_latency_includes_by_platform(self) -> dict[str, list[str]]:
        return self._rules.includes_by_platform

    @_serialized
    def set_device_capabilities(self, capabilities) -> None:
        """Forget the previous device's effective mode without sending packets."""
        if not self._device.set_capabilities(capabilities):
            return
        self.clear_latency_hold()
        self._publish_latency("device")
        self.refresh_device_state()

    def refresh_device_state(self) -> None:
        self._device.refresh(self._publish_latency)

    def get_display_state(self) -> dict:
        """Return the latest state for Home and the tray."""
        with self._lock:
            return self._device.display_state()

    def _publish_latency(self, source: str) -> None:
        self._publish(
            PubSubTopic.LATENCY,
            enabled=self.state["effective_low_latency"],
            mode=self.state["selected_mode"],
            source=source,
        )

    def _reapply_policy(self, source: str = "manual") -> None:
        last_state = self.state["last_monitor_state"]
        self.apply_monitor_latency_policy(
            bool(last_state.get("is_fullscreen", False)),
            str(last_state.get("app_id", "")),
            source=source,
        )

    def _status(self, text: str, color: str = "white") -> None:
        self._publish(PubSubTopic.STATUS, text=text, color=color)

    @_serialized
    def on_monitor_state(self, is_fullscreen: bool, app_id: str) -> None:
        self.state["last_monitor_state"] = {
            "is_fullscreen": is_fullscreen, "app_id": app_id,
        }
        self.apply_monitor_latency_policy(is_fullscreen, app_id, source="monitor")

    @_serialized
    def on_hold_released(self, app_id: str) -> None:
        self._device.sync()
        released_app = (app_id or "").strip().lower()
        active_hold = self.state["latency_hold_app_id"]
        if self.state["selected_mode"] != "auto" or not active_hold:
            return
        if released_app and active_hold != released_app:
            return
        self.clear_latency_hold()
        if self.state["effective_low_latency"] is not False:
            if self.set_effective_latency_state(False, source="auto_hold_release"):
                self._status(m("latency.app_closed"), "white")

    def active_low_latency_exceptions(self) -> set[str]:
        return set(self.low_latency_exceptions_by_platform.get(self.platform_key, []))

    def active_low_latency_includes(self) -> set[str]:
        return set(self.low_latency_includes_by_platform.get(self.platform_key, []))

    def is_process_running(self, app_id: str) -> bool:
        return is_process_running(app_id)

    @_serialized
    def clear_latency_hold(self) -> None:
        self._hold.clear()

    def start_hold_watcher_if_needed(self) -> None:
        self._hold.start()

    def stop(self) -> None:
        """Wake the hold watcher without changing saved latency preferences."""
        self._stopped.set()

    @_serialized
    def apply_monitor_latency_policy(self, is_fullscreen: bool, app_id: str, source: str = "monitor") -> None:
        controller = self._device.sync()
        if controller is not None and not controller.capabilities.supports("latency"):
            self.clear_latency_hold()
            self._device.invalidate()
            return
        decision = evaluate_policy(
            mode=self.state["selected_mode"], is_fullscreen=is_fullscreen, app_id=app_id,
            includes=self.active_low_latency_includes(), excludes=self.active_low_latency_exceptions(),
            hold_enabled=bool(self.state["hold_until_app_close_enabled"]),
            current_hold=self.state["latency_hold_app_id"], is_process_running=self.is_process_running,
        )
        if decision.hold_app is not None:
            if decision.hold_app:
                self.set_latency_hold(decision.hold_app)
            else:
                self.clear_latency_hold()

        if decision.enabled:
            if self.state["effective_low_latency"] is not True:
                if not self.set_effective_latency_state(True, source=source):
                    return
            if self._device.update_activation(decision.activation_app, controller):
                self._publish_latency(source)
            self._status(decision.status, "blue")
        else:
            if self._device.update_activation(""):
                self._publish_latency(source)
            if self.state["effective_low_latency"] is not False:
                if not self.set_effective_latency_state(False, source=source):
                    return
            self._status(decision.status, "white")

    @_serialized
    def set_effective_latency_state(self, new_state: bool, source: str = "manual") -> bool:
        controller = self._get_controller()
        if controller is not None and not controller.capabilities.supports("latency"):
            self.clear_latency_hold()
            self._device.invalidate()
            return False
        success, message = self._device.set_enabled(controller, new_state)
        if not success:
            self._status(message, "red")
            self._publish_latency(source)
            return False

        tray_inst = self._get_tray()
        if tray_inst:
            tray_inst.refresh_menu()
        self._publish_latency(source)
        return True

    @_serialized
    def set_selected_latency_mode(self, mode: str, source: str = "manual") -> None:
        normalized_mode = (mode or "").strip().lower()
        if normalized_mode not in {"off", "auto", "on"}:
            return

        self.state["selected_mode"] = normalized_mode
        set_low_latency_mode(normalized_mode)

        self._device.clear_error()
        self._reapply_policy(source)
        self._publish_latency(source)

        tray_inst = self._get_tray()
        if tray_inst:
            tray_inst.refresh_menu()

    @_serialized
    def set_hold_until_app_close_enabled(self, enabled: bool) -> None:
        self.state["hold_until_app_close_enabled"] = bool(enabled)
        set_low_latency_hold_until_app_close(enabled)
        self._reapply_policy()

    @_serialized
    def set_latency_hold(self, app_id: str) -> None:
        self._hold.set_app(app_id)

    def select_latency_mode_from_tray(self, mode: str) -> None:
        self.set_selected_latency_mode(mode, source="tray")

    @_serialized
    def toggle_latency_from_tray(self, session) -> None:
        """Cycle the selected policy through On, Off, and Auto."""
        controller = self._get_controller()
        if (controller is None or not controller.connected or controller.eq_session != session
                or not controller.capabilities.supports("latency")):
            return
        next_mode = {"on": "off", "off": "auto", "auto": "on"}
        self.set_selected_latency_mode(
            next_mode.get(self.state["selected_mode"], "on"), source="tray")

    def on_latency_mode_change(self, e):
        selected = str(getattr(e.control, "value", "off"))
        self.set_selected_latency_mode(selected, source="manual")

    @_serialized
    def _change_rule(self, platform: str, value: str, mode: str) -> None:
        change = self._rules.change(platform, value, mode)
        if change is None:
            return
        target_platform, normalized, excluded_sorted, included_sorted = change
        self._on_rules_change(target_platform, excluded_sorted, included_sorted)
        if target_platform == self.platform_key:
            if self.state["latency_hold_app_id"] == normalized and mode != "include":
                self.clear_latency_hold()
            self._reapply_policy(source="rules")

    def on_add_low_latency_list_item(self, platform: str, value: str):
        self._change_rule(platform, value, "exclude")

    def on_remove_low_latency_list_item(self, platform: str, value: str):
        self._change_rule(platform, value, "remove")

    def on_set_low_latency_item_mode(self, platform: str, value: str, mode: str):
        selected_mode = (mode or "").strip().lower()
        if selected_mode in {"exclude", "include"}:
            self._change_rule(platform, value, selected_mode)

    def on_add_low_latency_include_item(self, platform: str, value: str):
        self._change_rule(platform, value, "include")

    def on_wait_until_app_close_change(self, e):
        enabled = bool(e.control.value)
        self.set_hold_until_app_close_enabled(enabled)
        self._status(
            m("latency.wait_enabled" if enabled else "latency.wait_disabled"),
            "green" if enabled else "white",
        )
        self._on_ui_update()
