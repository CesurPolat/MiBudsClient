"""Low latency mode policy, app rules, and hold-until-close handling."""

from utils.i18n import message as m, error_message

import subprocess
import sys
import threading
import time
from typing import Callable
from functools import wraps

from utils.user_preferences import (
    get_all_low_latency_exceptions,
    get_all_low_latency_includes,
    set_low_latency_exceptions,
    set_low_latency_includes,
    get_low_latency_mode,
    set_low_latency_mode,
    get_low_latency_hold_until_app_close,
    set_low_latency_hold_until_app_close,
)


def _serialized(method):
    """Serialize state changes originating from tray, UI, and monitor callbacks."""
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


class LatencyController:
    """Coordinate mode changes through callbacks, independently of Flet controls."""

    def __init__(self, publish: Callable, get_controller: Callable,
                 get_tray: Callable, on_rules_change: Callable,
                 on_ui_update: Callable):
        self._lock = threading.RLock()
        self._last_error = None
        self._publish = publish
        self._get_controller = get_controller
        self._get_tray = get_tray
        self._on_rules_change = on_rules_change
        self._on_ui_update = on_ui_update
        self.state = {
            "selected_mode": get_low_latency_mode(),
            "effective_low_latency": False,
            "latency_hold_app_id": "",
            "hold_watcher_running": False,
            "hold_until_app_close_enabled": get_low_latency_hold_until_app_close(),
            "last_monitor_state": {"is_fullscreen": False, "app_id": ""},
        }
        self.platform_key = "windows" if sys.platform.startswith("win") else "linux"
        self.low_latency_exceptions_by_platform = get_all_low_latency_exceptions()
        self.low_latency_includes_by_platform = get_all_low_latency_includes()

    def get_display_state(self) -> dict:
        """Return the current controller-owned state, rather than a queued message."""
        with self._lock:
            return {
                "mode": self.state["selected_mode"],
                "enabled": self.state["effective_low_latency"],
                "error": self._last_error,
            }

    def _publish_latency(self, source: str) -> None:
        self._publish({
            "type": "latency",
            "enabled": self.state["effective_low_latency"],
            "mode": self.state["selected_mode"],
            "source": source,
        })

    def _reapply_policy(self, source: str = "manual") -> None:
        last_state = self.state["last_monitor_state"]
        self.apply_monitor_latency_policy(
            bool(last_state.get("is_fullscreen", False)),
            str(last_state.get("app_id", "")),
            source=source,
        )

    def _status(self, text: str, color: str = "white") -> None:
        self._publish({"type": "status", "text": text, "color": color})

    @_serialized
    def on_monitor_state(self, is_fullscreen: bool, app_id: str) -> None:
        self.state["last_monitor_state"] = {
            "is_fullscreen": is_fullscreen, "app_id": app_id,
        }
        self.apply_monitor_latency_policy(is_fullscreen, app_id, source="monitor")

    @_serialized
    def on_hold_released(self, app_id: str) -> None:
        released_app = (app_id or "").strip().lower()
        active_hold = self.state["latency_hold_app_id"]
        if self.state["selected_mode"] != "auto" or not active_hold:
            return
        if released_app and active_hold != released_app:
            return
        self.clear_latency_hold()
        if self.state["effective_low_latency"]:
            if self.set_effective_latency_state(False, source="auto_hold_release"):
                self._status(m("latency.app_closed"), "white")

    def active_low_latency_exceptions(self) -> set[str]:
        return set(self.low_latency_exceptions_by_platform.get(self.platform_key, []))

    def active_low_latency_includes(self) -> set[str]:
        return set(self.low_latency_includes_by_platform.get(self.platform_key, []))

    def is_process_running(self, app_id: str) -> bool:
        app_name = (app_id or "").strip().lower()
        if not app_name:
            return False

        try:
            if sys.platform.startswith("win"):
                startupinfo = None
                creationflags = 0
                if hasattr(subprocess, "STARTUPINFO"):
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                if hasattr(subprocess, "CREATE_NO_WINDOW"):
                    creationflags |= subprocess.CREATE_NO_WINDOW

                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {app_name}"],
                    capture_output=True,
                    text=True,
                    startupinfo=startupinfo,
                    creationflags=creationflags,
                    check=False,
                )
                output = (result.stdout or "").lower()
                return app_name in output and "no tasks are running" not in output

            if sys.platform.startswith("linux"):
                result = subprocess.run(
                    ["pgrep", "-f", app_name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return result.returncode == 0 and bool((result.stdout or "").strip())
        except Exception:
            return False

        return False

    @_serialized
    def clear_latency_hold(self) -> None:
        self.state["latency_hold_app_id"] = ""

    @_serialized
    def start_hold_watcher_if_needed(self) -> None:
        if self.state["hold_watcher_running"]:
            return

        hold_app_id = self.state["latency_hold_app_id"]
        if not hold_app_id:
            return

        if self.state["selected_mode"] != "auto":
            return

        if not self.state["hold_until_app_close_enabled"]:
            return

        self.state["hold_watcher_running"] = True

        def _watcher() -> None:
            try:
                while True:
                    if self.state["selected_mode"] != "auto":
                        return

                    if not self.state["hold_until_app_close_enabled"]:
                        return

                    current_hold = self.state["latency_hold_app_id"]
                    if not current_hold:
                        return

                    if not self.is_process_running(current_hold):
                        self._publish({"type": "auto_hold_released", "app_id": current_hold})
                        return

                    time.sleep(2)
            finally:
                with self._lock:
                    self.state["hold_watcher_running"] = False

        threading.Thread(target=_watcher, daemon=True).start()

    @_serialized
    def apply_monitor_latency_policy(self, is_fullscreen: bool, app_id: str, source: str = "monitor") -> None:
        normalized_app = (app_id or "").strip().lower()
        selected_mode = self.state["selected_mode"]
        hold_enabled = bool(self.state["hold_until_app_close_enabled"])
        current_hold = self.state["latency_hold_app_id"]

        def enable_low_latency(message: str, color: str = "blue") -> None:
            if not self.state["effective_low_latency"]:
                if not self.set_effective_latency_state(True, source=source):
                    return
            self._status(message, color)

        def disable_low_latency(message: str = m("latency.standard_restored")) -> None:
            if self.state["effective_low_latency"]:
                if not self.set_effective_latency_state(False, source=source):
                    return
            self._status(message, "white")

        if selected_mode == "on":
            self.clear_latency_hold()
            enable_low_latency(m("latency.enabled"), "blue")
            return

        if selected_mode == "off":
            self.clear_latency_hold()
            disable_low_latency()
            return

        if selected_mode == "auto":
            included_apps = self.active_low_latency_includes()
            excluded_apps = self.active_low_latency_exceptions()
            include_match = bool(normalized_app and normalized_app in included_apps)
            exclude_match = bool(normalized_app and normalized_app in excluded_apps)
            fullscreen_match = bool(is_fullscreen and normalized_app and not exclude_match)
            matches = include_match or fullscreen_match

            if include_match:
                enable_message = m("latency.included")
            else:
                enable_message = m("latency.fullscreen")

            if exclude_match:
                disable_message = m("latency.skipped", app=normalized_app)
            elif include_match:
                disable_message = m("latency.include_left")
            else:
                disable_message = m("latency.fullscreen_ended")

            if matches:
                if hold_enabled:
                    self.set_latency_hold(normalized_app)
                else:
                    self.clear_latency_hold()
                enable_low_latency(enable_message, "blue")
                return

            if hold_enabled and current_hold and self.is_process_running(current_hold):
                enable_low_latency(m("latency.keeping", app=current_hold), "blue")
                return

            self.clear_latency_hold()
            disable_low_latency(disable_message)
            return

        self.clear_latency_hold()
        disable_low_latency()

    @_serialized
    def set_effective_latency_state(self, new_state: bool, source: str = "manual") -> bool:
        controller = self._get_controller()
        try:
            if controller is None:
                success, message = False, m("latency.unavailable")
            else:
                success, message = controller.send_command("low" if new_state else "std")
        except Exception as exc:
            success, message = False, m("latency.failed", details=error_message(exc))

        if not success:
            self._last_error = message
            self._status(message, "red")
            self._publish_latency(source)
            return False

        self._last_error = None
        self.state["effective_low_latency"] = bool(new_state)
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

        self._last_error = None
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
        normalized = (app_id or "").strip().lower()
        if not normalized:
            return
        if not self.state["hold_until_app_close_enabled"]:
            return
        self.state["latency_hold_app_id"] = normalized
        self.start_hold_watcher_if_needed()

    def select_latency_mode_from_tray(self, mode: str) -> None:
        self.set_selected_latency_mode(mode, source="tray")

    def on_latency_mode_change(self, e):
        selected = str(getattr(e.control, "value", "off"))
        self.set_selected_latency_mode(selected, source="manual")

    @_serialized
    def _change_rule(self, platform: str, value: str, mode: str) -> None:
        target_platform = (platform or "").strip().lower()
        normalized = (value or "").strip().lower()
        if target_platform not in {"windows", "linux"} or not normalized:
            return
        if mode not in {"exclude", "include", "remove"}:
            return
        excluded = set(self.low_latency_exceptions_by_platform.get(target_platform, []))
        included = set(self.low_latency_includes_by_platform.get(target_platform, []))
        excluded.discard(normalized)
        included.discard(normalized)
        if mode == "exclude":
            excluded.add(normalized)
        elif mode == "include":
            included.add(normalized)
        excluded_sorted, included_sorted = sorted(excluded), sorted(included)
        self.low_latency_exceptions_by_platform[target_platform] = excluded_sorted
        self.low_latency_includes_by_platform[target_platform] = included_sorted
        set_low_latency_exceptions(excluded_sorted, platform=target_platform)
        set_low_latency_includes(included_sorted, platform=target_platform)
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
