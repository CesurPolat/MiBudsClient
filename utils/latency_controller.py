"""Low latency mode policy, app rules, and hold-until-close handling."""

import subprocess
import sys
import threading
import time
from typing import Callable

from .user_preferences import (
    get_all_low_latency_exceptions,
    get_all_low_latency_includes,
    set_low_latency_exceptions,
    set_low_latency_includes,
    get_low_latency_mode,
    set_low_latency_mode,
    get_low_latency_hold_until_app_close,
    set_low_latency_hold_until_app_close,
)


class LatencyController:
    """Coordinate mode changes through callbacks, independently of Flet controls."""

    def __init__(self, publish: Callable, get_controller: Callable,
                 get_tray: Callable, on_rules_change: Callable,
                 on_ui_update: Callable):
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

    def _status(self, text: str, color: str = "white") -> None:
        self._publish({"type": "status", "text": text, "color": color})

    def on_monitor_state(self, is_fullscreen: bool, app_id: str) -> None:
        self.state["last_monitor_state"] = {
            "is_fullscreen": is_fullscreen, "app_id": app_id,
        }
        self.apply_monitor_latency_policy(is_fullscreen, app_id, source="monitor")

    def on_hold_released(self, app_id: str) -> None:
        released_app = (app_id or "").strip().lower()
        active_hold = self.state["latency_hold_app_id"]
        if self.state["selected_mode"] != "auto" or not active_hold:
            return
        if released_app and active_hold != released_app:
            return
        self.clear_latency_hold()
        if self.state["effective_low_latency"]:
            self.set_effective_latency_state(False, source="auto_hold_release")
            self._status("Tracked app closed. Standard mode restored", "white")

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

    def clear_latency_hold(self) -> None:
        self.state["latency_hold_app_id"] = ""

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
                self.state["hold_watcher_running"] = False

        threading.Thread(target=_watcher, daemon=True).start()

    def apply_monitor_latency_policy(self, is_fullscreen: bool, app_id: str, source: str = "monitor") -> None:
        normalized_app = (app_id or "").strip().lower()
        selected_mode = self.state["selected_mode"]
        hold_enabled = bool(self.state["hold_until_app_close_enabled"])
        current_hold = self.state["latency_hold_app_id"]

        def enable_low_latency(message: str, color: str = "blue") -> None:
            if not self.state["effective_low_latency"]:
                self.set_effective_latency_state(True, source=source)
            self._status(message, color)

        def disable_low_latency(message: str = "Standard mode restored") -> None:
            if self.state["effective_low_latency"]:
                self.set_effective_latency_state(False, source=source)
            self._status(message, "white")

        if selected_mode == "on":
            self.clear_latency_hold()
            enable_low_latency("Low Latency enabled", "blue")
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
                enable_message = "Included app detected. Low Latency enabled"
            else:
                enable_message = "Fullscreen detected. Low Latency enabled"

            if exclude_match:
                disable_message = f"Auto low latency skipped for {normalized_app}"
            elif include_match:
                disable_message = "Included app left. Standard mode restored"
            else:
                disable_message = "Fullscreen ended. Standard mode restored"

            if matches:
                if hold_enabled:
                    self.set_latency_hold(normalized_app)
                else:
                    self.clear_latency_hold()
                enable_low_latency(enable_message, "blue")
                return

            if hold_enabled and current_hold and self.is_process_running(current_hold):
                enable_low_latency(f"Keeping Low Latency until {current_hold} closes", "blue")
                return

            self.clear_latency_hold()
            disable_low_latency(disable_message)
            return

        self.clear_latency_hold()
        disable_low_latency()

    def set_effective_latency_state(self, new_state: bool, source: str = "manual") -> None:
        self.state["effective_low_latency"] = bool(new_state)

        if self._get_controller():
            mode = "low" if new_state else "std"
            success, message = self._get_controller().send_command(mode)
            if not success:
                self._publish({"type": "status", "text": message, "color": "red"})

        tray_inst = self._get_tray()
        if tray_inst:
            tray_inst.refresh_menu()

        self._publish(
            {
                "type": "latency",
                "enabled": bool(new_state),
                "mode": self.state["selected_mode"],
                "source": source,
            }
        )

    def set_selected_latency_mode(self, mode: str, source: str = "manual") -> None:
        normalized_mode = (mode or "").strip().lower()
        if normalized_mode not in {"off", "auto", "on"}:
            return

        self.state["selected_mode"] = normalized_mode
        set_low_latency_mode(normalized_mode)

        last_state = self.state.get("last_monitor_state", {})
        self.apply_monitor_latency_policy(
            bool(last_state.get("is_fullscreen", False)),
            str(last_state.get("app_id", "")),
            source=source,
        )

        tray_inst = self._get_tray()
        if tray_inst:
            tray_inst.refresh_menu()

    def set_hold_until_app_close_enabled(self, enabled: bool) -> None:
        self.state["hold_until_app_close_enabled"] = bool(enabled)
        set_low_latency_hold_until_app_close(enabled)
        last_state = self.state.get("last_monitor_state", {})
        self.apply_monitor_latency_policy(
            bool(last_state.get("is_fullscreen", False)),
            str(last_state.get("app_id", "")),
            source="manual",
        )

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

    def on_add_low_latency_list_item(self, platform: str, value: str):
        target_platform = (platform or "").strip().lower()
        if target_platform not in {"windows", "linux"}:
            return
        normalized = (value or "").strip().lower()
        if not normalized:
            return
        excluded_values = set(self.low_latency_exceptions_by_platform.get(target_platform, []))
        included_values = set(self.low_latency_includes_by_platform.get(target_platform, []))
        included_values.discard(normalized)
        excluded_values.add(normalized)
        excluded_sorted = sorted(excluded_values)
        included_sorted = sorted(included_values)
        self.low_latency_exceptions_by_platform[target_platform] = excluded_sorted
        self.low_latency_includes_by_platform[target_platform] = included_sorted
        set_low_latency_exceptions(excluded_sorted, platform=target_platform)
        set_low_latency_includes(included_sorted, platform=target_platform)
        self._on_rules_change(target_platform, excluded_sorted, included_sorted)

    def on_remove_low_latency_list_item(self, platform: str, value: str):
        target_platform = (platform or "").strip().lower()
        if target_platform not in {"windows", "linux"}:
            return
        normalized = (value or "").strip().lower()
        if not normalized:
            return
        excluded_values = set(self.low_latency_exceptions_by_platform.get(target_platform, []))
        included_values = set(self.low_latency_includes_by_platform.get(target_platform, []))
        excluded_values.discard(normalized)
        included_values.discard(normalized)
        excluded_sorted = sorted(excluded_values)
        included_sorted = sorted(included_values)
        self.low_latency_exceptions_by_platform[target_platform] = excluded_sorted
        self.low_latency_includes_by_platform[target_platform] = included_sorted
        set_low_latency_exceptions(excluded_sorted, platform=target_platform)
        set_low_latency_includes(included_sorted, platform=target_platform)
        self._on_rules_change(target_platform, excluded_sorted, included_sorted)

    def on_set_low_latency_item_mode(self, platform: str, value: str, mode: str):
        target_platform = (platform or "").strip().lower()
        normalized = (value or "").strip().lower()
        selected_mode = (mode or "").strip().lower()
        if target_platform not in {"windows", "linux"} or not normalized:
            return
        if selected_mode not in {"exclude", "include"}:
            return

        excluded_values = set(self.low_latency_exceptions_by_platform.get(target_platform, []))
        included_values = set(self.low_latency_includes_by_platform.get(target_platform, []))
        excluded_values.discard(normalized)
        included_values.discard(normalized)

        if selected_mode == "exclude":
            excluded_values.add(normalized)
        else:
            included_values.add(normalized)

        excluded_sorted = sorted(excluded_values)
        included_sorted = sorted(included_values)
        self.low_latency_exceptions_by_platform[target_platform] = excluded_sorted
        self.low_latency_includes_by_platform[target_platform] = included_sorted
        set_low_latency_exceptions(excluded_sorted, platform=target_platform)
        set_low_latency_includes(included_sorted, platform=target_platform)
        self._on_rules_change(target_platform, excluded_sorted, included_sorted)

        last_state = self.state.get("last_monitor_state", {})
        self.apply_monitor_latency_policy(
            bool(last_state.get("is_fullscreen", False)),
            str(last_state.get("app_id", "")),
            source="manual",
        )

    def on_add_low_latency_include_item(self, platform: str, value: str):
        self.on_add_low_latency_list_item(platform, value)
        self.on_set_low_latency_item_mode(platform, value, "include")

    def on_wait_until_app_close_change(self, e):
        enabled = bool(e.control.value)
        self.set_hold_until_app_close_enabled(enabled)
        self._status(
            f"Wait until app closes {'enabled' if enabled else 'disabled'}",
            "green" if enabled else "white",
        )
        self._on_ui_update()
