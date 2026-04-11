"""Mi Buds Client - Main Application Entry Point."""

import flet as ft
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser

try:
    import winsound
except ImportError:
    winsound = None

from bluetooth import BTController
from utils import (
    set_startup, 
    is_startup_enabled, 
    check_for_updates,
    should_show_update_notification,
    suppress_update_notification,
    get_all_low_latency_exceptions,
    get_all_low_latency_includes,
    set_low_latency_exceptions,
    set_low_latency_includes,
    get_low_latency_mode,
    set_low_latency_mode,
    get_low_latency_hold_until_app_close,
    set_low_latency_hold_until_app_close,
    check_for_existing_instance,
    start_instance_listener
)
from ui import (
    APP_TITLE, APP_VERSION, GITHUB_URL, WINDOW_WIDTH, WINDOW_HEIGHT, COLOR_BG, COLOR_CARD_BG,
    BATTERY_UNKNOWN, BATTERY_CHARGING_OFFSET, WindowManager, SystemTray
)
from ui.components import (
    AppTitle, DeviceImage, BatteryPanel, SettingsCard, StatusBar, Spacer, Footer
)
from utils.debug_console import DebugConsoleManager
from utils.game_monitor import FullscreenGameMonitor


def main(page: ft.Page):
    """Main application entry point."""
    debug_console = DebugConsoleManager()
    debug_console.install()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Page Configuration
    # ─────────────────────────────────────────────────────────────────────────
    page.title = APP_TITLE
    page.bgcolor = COLOR_BG
    page.padding = 20
    
    # Newer Flet API properties
    page.window.width = WINDOW_WIDTH
    page.window.height = WINDOW_HEIGHT
    page.window.min_width = WINDOW_WIDTH
    page.window.min_height = WINDOW_HEIGHT
    page.window.max_width = WINDOW_WIDTH
    page.window.max_height = WINDOW_HEIGHT
    page.window.resizable = page.platform != ft.PagePlatform.WINDOWS
    page.window.maximizable = False
    page.window.icon = "icon.ico" if page.platform == ft.PagePlatform.WINDOWS else "icon.png"  # Path relative to assets_dir
    
    page.scroll = "auto"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # Initialize Managers
    # ─────────────────────────────────────────────────────────────────────────
    window_mgr = WindowManager(page)
    
    # Controller will be set after initialization
    controller_ref = {
        "instance": None,
        "selected_mode": get_low_latency_mode(),
        "effective_low_latency": False,
        "reconnect_in_progress": False,
        "game_monitor": None,
        "latency_hold_app_id": "",
        "hold_watcher_running": False,
        "hold_until_app_close_enabled": get_low_latency_hold_until_app_close(),
        "last_monitor_state": {"is_fullscreen": False, "app_id": ""},
    }
    platform_key = "windows" if sys.platform.startswith("win") else "linux"
    low_latency_exceptions_by_platform = get_all_low_latency_exceptions()
    low_latency_includes_by_platform = get_all_low_latency_includes()

    def active_low_latency_exceptions() -> set[str]:
        return set(low_latency_exceptions_by_platform.get(platform_key, []))

    def active_low_latency_includes() -> set[str]:
        return set(low_latency_includes_by_platform.get(platform_key, []))

    notification_state = {
        "last_connection_event": None
    }

    tray_ref = {
        "instance": None
    }

    debug_state = {
        "last_toggle_at": 0.0
    }

    def is_process_running(app_id: str) -> bool:
        app_name = (app_id or "").strip().lower()
        if not app_name:
            return False

        try:
            if sys.platform.startswith("win"):
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {app_name}"],
                    capture_output=True,
                    text=True,
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

    def clear_latency_hold() -> None:
        controller_ref["latency_hold_app_id"] = ""

    def start_hold_watcher_if_needed() -> None:
        if controller_ref["hold_watcher_running"]:
            return

        hold_app_id = controller_ref["latency_hold_app_id"]
        if not hold_app_id:
            return

        if controller_ref["selected_mode"] != "auto":
            return

        if not controller_ref["hold_until_app_close_enabled"]:
            return

        controller_ref["hold_watcher_running"] = True

        def _watcher() -> None:
            try:
                while True:
                    if controller_ref["selected_mode"] != "auto":
                        return

                    if not controller_ref["hold_until_app_close_enabled"]:
                        return

                    current_hold = controller_ref["latency_hold_app_id"]
                    if not current_hold:
                        return

                    if not is_process_running(current_hold):
                        page.pubsub.send_all({"type": "auto_hold_released", "app_id": current_hold})
                        return

                    time.sleep(2)
            finally:
                controller_ref["hold_watcher_running"] = False

        threading.Thread(target=_watcher, daemon=True).start()

    def apply_monitor_latency_policy(is_fullscreen: bool, app_id: str, source: str = "monitor") -> None:
        normalized_app = (app_id or "").strip().lower()
        selected_mode = controller_ref["selected_mode"]
        hold_enabled = bool(controller_ref["hold_until_app_close_enabled"])
        current_hold = controller_ref["latency_hold_app_id"]

        def enable_low_latency(message: str, color: str = "blue") -> None:
            if not controller_ref["effective_low_latency"]:
                set_effective_latency_state(True, source=source)
            update_status(message, color)

        def disable_low_latency(message: str = "Standard mode restored") -> None:
            if controller_ref["effective_low_latency"]:
                set_effective_latency_state(False, source=source)
            update_status(message, "white")

        if selected_mode == "on":
            clear_latency_hold()
            enable_low_latency("Low Latency enabled", "blue")
            return

        if selected_mode == "off":
            clear_latency_hold()
            disable_low_latency()
            return

        if selected_mode == "auto":
            included_apps = active_low_latency_includes()
            excluded_apps = active_low_latency_exceptions()
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
                    set_latency_hold(normalized_app)
                else:
                    clear_latency_hold()
                enable_low_latency(enable_message, "blue")
                return

            if hold_enabled and current_hold and is_process_running(current_hold):
                enable_low_latency(f"Keeping Low Latency until {current_hold} closes", "blue")
                return

            clear_latency_hold()
            disable_low_latency(disable_message)
            return

        clear_latency_hold()
        disable_low_latency()

    def set_effective_latency_state(new_state: bool, source: str = "manual") -> None:
        controller_ref["effective_low_latency"] = bool(new_state)

        if controller_ref["instance"]:
            mode = "low" if new_state else "std"
            success, message = controller_ref["instance"].send_command(mode)
            if not success:
                page.pubsub.send_all({"type": "status", "text": message, "color": "red"})

        tray_inst = tray_ref["instance"]
        if tray_inst:
            tray_inst.refresh_menu()

        page.pubsub.send_all(
            {
                "type": "latency",
                "enabled": bool(new_state),
                "mode": controller_ref["selected_mode"],
                "source": source,
            }
        )

    def set_selected_latency_mode(mode: str, source: str = "manual") -> None:
        normalized_mode = (mode or "").strip().lower()
        if normalized_mode not in {"off", "auto", "on"}:
            return

        controller_ref["selected_mode"] = normalized_mode
        set_low_latency_mode(normalized_mode)

        last_state = controller_ref.get("last_monitor_state", {})
        apply_monitor_latency_policy(
            bool(last_state.get("is_fullscreen", False)),
            str(last_state.get("app_id", "")),
            source=source,
        )

        tray_inst = tray_ref["instance"]
        if tray_inst:
            tray_inst.refresh_menu()

    def set_hold_until_app_close_enabled(enabled: bool) -> None:
        controller_ref["hold_until_app_close_enabled"] = bool(enabled)
        set_low_latency_hold_until_app_close(enabled)
        last_state = controller_ref.get("last_monitor_state", {})
        apply_monitor_latency_policy(
            bool(last_state.get("is_fullscreen", False)),
            str(last_state.get("app_id", "")),
            source="manual",
        )

    def set_latency_hold(app_id: str) -> None:
        normalized = (app_id or "").strip().lower()
        if not normalized:
            return
        if not controller_ref["hold_until_app_close_enabled"]:
            return
        controller_ref["latency_hold_app_id"] = normalized
        start_hold_watcher_if_needed()

    def select_latency_mode_from_tray(mode: str) -> None:
        set_selected_latency_mode(mode, source="tray")

    def tray_exit_request() -> None:
        page.pubsub.send_all({"type": "app", "action": "close"})

    tray = SystemTray(
        on_show=window_mgr.show,
        on_exit=tray_exit_request,
        on_latency_mode_select=select_latency_mode_from_tray,
        get_latency_mode=lambda: controller_ref["selected_mode"],
    )
    tray_ref["instance"] = tray
    threading.Thread(target=tray.run, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    # Create UI Components
    # ─────────────────────────────────────────────────────────────────────────
    title = AppTitle(APP_TITLE)
    device_image = DeviceImage()
    battery_panel = BatteryPanel()
    status_bar = StatusBar()
    status_bar.size = 11
    device_status_card = ft.Container(
        content=ft.Row(
            controls=[
                device_image,
                ft.Column(
                    controls=[status_bar, battery_panel],
                    spacing=6,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                    expand=True,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=12, vertical=10),
        bgcolor=COLOR_CARD_BG,
        border_radius=18,
        border=ft.border.all(1, "#2B313C"),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Message Handlers
    # ─────────────────────────────────────────────────────────────────────────
    def on_pubsub_message(message):
        """Handle pubsub messages for cross-thread UI updates."""
        if not isinstance(message, dict):
            return
        
        msg_type = message.get("type")
        
        if msg_type == "status":
            status_bar.update_status(
                message.get("text", ""),
                message.get("color", "white")
            )
            page.update()
        
        elif msg_type == "battery":
            left = message.get("left", BATTERY_UNKNOWN)
            right = message.get("right", BATTERY_UNKNOWN)
            case = message.get("case", BATTERY_UNKNOWN)
            transient = message.get("transient", False)

            battery_panel.update_all(left, right, case)

            if transient:
                status_bar.update_status("Refreshing battery data...", "white")
            else:
                status_bar.update_status("Battery data updated", "green")

            page.update()
        
        elif msg_type == "window":
            action = message.get("action")
            if action == "show":
                window_mgr.apply_show()
                reconnect_if_disconnected_on_show()
            elif action == "hide":
                window_mgr.apply_hide()
        
        elif msg_type == "latency":
            enabled = bool(message.get("enabled"))
            mode = str(message.get("mode", controller_ref["selected_mode"]))
            controller_ref["effective_low_latency"] = enabled
            controller_ref["selected_mode"] = mode

            settings_card.set_latency_mode(mode)
            if mode == "auto":
                mode_text = "Automatic"
                color = "blue" if enabled else "white"
            elif mode == "on":
                mode_text = "Low Latency"
                color = "blue"
            else:
                mode_text = "Standard"
                color = "white"

            update_status(f"{mode_text} mode set", color)
            page.update()

        elif msg_type == "auto_hold_released":
            released_app = str(message.get("app_id", "")).strip().lower()
            active_hold = controller_ref["latency_hold_app_id"]
            if controller_ref["selected_mode"] != "auto" or not active_hold:
                return
            if released_app and active_hold != released_app:
                return

            clear_latency_hold()
            if controller_ref["effective_low_latency"]:
                set_effective_latency_state(False, source="auto_hold_release")
                update_status("Tracked app closed. Standard mode restored", "white")

        elif msg_type == "update_notification":
            latest_ver = message.get("latest_ver")
            if not latest_ver:
                return

            def on_dont_show_again_change(e):
                if e.control.value:
                    suppress_update_notification(latest_ver)

            def on_update_click(e):
                webbrowser.open(GITHUB_URL)
                snack_bar.open = False
                page.update()

            snack_bar = ft.SnackBar(
                content=ft.Row(
                    controls=[
                        ft.Text(
                            f"New version available: {latest_ver}",
                            color="white",
                            expand=True,
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Row(
                            controls=[
                                ft.Checkbox(
                                    label=None,
                                    value=False,
                                    fill_color="white",
                                    check_color="#171717",
                                    width=20,
                                    height=20,
                                    on_change=on_dont_show_again_change,
                                ),
                                ft.Text(
                                    "Don't show again",
                                    color="white",
                                    size=12,
                                    no_wrap=True,
                                ),
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.ElevatedButton(
                            "Download",
                            icon=ft.Icons.DOWNLOAD,
                            on_click=on_update_click,
                            style=ft.ButtonStyle(
                                color="white",
                                bgcolor="#2E7D32",
                            ),
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                duration=10000,
                bgcolor="#171717",
                show_close_icon=True,
                close_icon_color="white"
            )
            page.overlay.append(snack_bar)
            snack_bar.open = True
            page.update()

        elif msg_type == "app" and message.get("action") == "close":
            game_monitor = controller_ref.get("game_monitor")
            if game_monitor:
                game_monitor.stop()
            debug_console.stop_f12_hotkey_listener()
            window_mgr.close()

        elif msg_type == "debug_console":
            action = message.get("action")
            if action != "toggle":
                return

            now = time.monotonic()
            if now - debug_state["last_toggle_at"] < 0.35:
                return
            debug_state["last_toggle_at"] = now

            result = debug_console.toggle_console()
            if result == "opened":
                status_bar.update_status("Debug console opened", "blue")
            elif result == "closed":
                status_bar.update_status("Debug console closed", "white")
            else:
                status_bar.update_status("Debug console could not be opened", "red")
            page.update()

        elif msg_type == "connection_event":
            event = message.get("event")
            if event == notification_state["last_connection_event"]:
                return

            notification_state["last_connection_event"] = event
            if event == "connected":
                tray.notify("Earbuds connected")
            elif event == "disconnected":
                clear_latency_hold()
                tray.notify("Earbuds disconnected")

        elif msg_type == "fullscreen_state":
            is_fullscreen = bool(message.get("is_fullscreen", False))
            app_id = str(message.get("app_id", "")).strip().lower()
            controller_ref["last_monitor_state"] = {
                "is_fullscreen": is_fullscreen,
                "app_id": app_id,
            }
            apply_monitor_latency_policy(is_fullscreen, app_id, source="monitor")

    page.pubsub.subscribe(on_pubsub_message)

    # ─────────────────────────────────────────────────────────────────────────
    # Controller Callbacks
    # ─────────────────────────────────────────────────────────────────────────
    previous_charging_state = {
        "left": None,
        "right": None,
    }

    def get_charging_state(raw_value):
        """Return charging state for a raw battery value, or None if unknown."""
        if raw_value == BATTERY_UNKNOWN:
            return None
        return raw_value >= BATTERY_CHARGING_OFFSET

    def play_charge_transition_sound(started):
        """Play distinct tone patterns for charge transitions on Windows/Linux."""
        start_pattern = [(880, 80), (1175, 90), (1568, 120)]
        stop_pattern = [(1568, 80), (1175, 90), (880, 120)]
        tones = start_pattern if started else stop_pattern

        def _play_tones():
            if winsound and sys.platform.startswith("win"):
                try:
                    for frequency, duration in tones:
                        winsound.Beep(frequency, duration)
                    return
                except RuntimeError:
                    winsound.MessageBeep(winsound.MB_OK)
                    return

            if sys.platform.startswith("linux"):
                play_bin = shutil.which("play")
                beep_bin = shutil.which("beep")

                if play_bin:
                    for frequency, duration in tones:
                        subprocess.run(
                            [
                                play_bin,
                                "-nq",
                                "synth",
                                f"{duration / 1000:.3f}",
                                "sine",
                                str(frequency),
                            ],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                        )
                    return

                if beep_bin:
                    for frequency, duration in tones:
                        subprocess.run(
                            [beep_bin, "-f", str(frequency), "-l", str(duration)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                        )
                    return

            # Last-resort fallback: terminal bell pattern.
            for _, duration in tones:
                try:
                    sys.stdout.write("\a")
                    sys.stdout.flush()
                except Exception:
                    pass
                time.sleep(duration / 1000)

        threading.Thread(target=_play_tones, daemon=True).start()

    def update_battery_ui(left, right, case):
        current_charging_state = {
            "left": get_charging_state(left),
            "right": get_charging_state(right),
        }

        for side in ("left", "right"):
            previous_state = previous_charging_state[side]
            current_state = current_charging_state[side]

            if previous_state is None or current_state is None:
                previous_charging_state[side] = current_state
                continue

            if not previous_state and current_state:
                play_charge_transition_sound(started=True)
            elif previous_state and not current_state:
                play_charge_transition_sound(started=False)

            previous_charging_state[side] = current_state

        # UX hint: briefly clear battery fields before showing the latest values,
        # even when values are unchanged.
        page.pubsub.send_all({
            "type": "battery",
            "left": BATTERY_UNKNOWN,
            "right": BATTERY_UNKNOWN,
            "case": BATTERY_UNKNOWN,
            "transient": True
        })
        time.sleep(0.2)
        page.pubsub.send_all({
            "type": "battery", 
            "left": left, 
            "right": right, 
            "case": case,
            "transient": False
        })

    def update_status(text, color="white"):
        page.pubsub.send_all({
            "type": "status", 
            "text": text, 
            "color": color
        })

    def request_battery_delayed():
        time.sleep(1)
        controller.resume_reconnect_attempts()
        controller.request_battery()

    def reconnect_if_disconnected_on_show():
        """When window is shown from tray, trigger an immediate reconnect attempt if disconnected."""
        if not controller.connected and not controller_ref["reconnect_in_progress"]:
            controller_ref["reconnect_in_progress"] = True

            def _reconnect_worker():
                try:
                    controller.resume_reconnect_attempts()
                    update_status("Connection lost. Reconnecting...", "orange")
                    controller.reconnect(force_rediscovery=True)
                finally:
                    controller_ref["reconnect_in_progress"] = False

            threading.Thread(target=_reconnect_worker, daemon=True).start()

    def on_keyboard_event(e):
        key_name = str(getattr(e, "key", "")).upper()
        if key_name != "F12":
            return

        if not sys.platform.startswith("win"):
            update_status("Debug console is currently supported on Windows", "orange")
            return

        page.pubsub.send_all({"type": "debug_console", "action": "toggle"})

    page.on_keyboard_event = on_keyboard_event
    debug_console.start_f12_hotkey_listener(
        lambda: page.pubsub.send_all({"type": "debug_console", "action": "toggle"})
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Initialize Bluetooth Controller
    # ─────────────────────────────────────────────────────────────────────────
    controller = BTController(
        status_callback=update_status,
        battery_callback=update_battery_ui,
        check_battery_callback=lambda: threading.Thread(
            target=request_battery_delayed, 
            daemon=True
        ).start(),
        connection_event_callback=lambda event: page.pubsub.send_all(
            {"type": "connection_event", "event": event}
        )
    )
    
    # Set controller reference for tray callbacks
    controller_ref["instance"] = controller

    # ─────────────────────────────────────────────────────────────────────────
    # Build Settings Card with Controller Actions
    # ─────────────────────────────────────────────────────────────────────────
    def on_startup_change(e):
        enabled = e.control.value
        if set_startup(enabled):
            update_status(
                f"Startup {'enabled' if enabled else 'disabled'}", 
                "green" if enabled else "white"
            )
        else:
            update_status("Failed to change startup setting", "red")
            e.control.value = not enabled
            page.update()

    def on_latency_mode_change(e):
        selected = str(getattr(e.control, "value", "off"))
        set_selected_latency_mode(selected, source="manual")

    def on_add_low_latency_list_item(platform: str, value: str):
        target_platform = (platform or "").strip().lower()
        if target_platform not in {"windows", "linux"}:
            return
        normalized = (value or "").strip().lower()
        if not normalized:
            return
        excluded_values = set(low_latency_exceptions_by_platform.get(target_platform, []))
        included_values = set(low_latency_includes_by_platform.get(target_platform, []))
        included_values.discard(normalized)
        excluded_values.add(normalized)
        excluded_sorted = sorted(excluded_values)
        included_sorted = sorted(included_values)
        low_latency_exceptions_by_platform[target_platform] = excluded_sorted
        low_latency_includes_by_platform[target_platform] = included_sorted
        set_low_latency_exceptions(excluded_sorted, platform=target_platform)
        set_low_latency_includes(included_sorted, platform=target_platform)
        settings_card.set_low_latency_rules(target_platform, excluded_sorted, included_sorted)

    def on_remove_low_latency_list_item(platform: str, value: str):
        target_platform = (platform or "").strip().lower()
        if target_platform not in {"windows", "linux"}:
            return
        normalized = (value or "").strip().lower()
        if not normalized:
            return
        excluded_values = set(low_latency_exceptions_by_platform.get(target_platform, []))
        included_values = set(low_latency_includes_by_platform.get(target_platform, []))
        excluded_values.discard(normalized)
        included_values.discard(normalized)
        excluded_sorted = sorted(excluded_values)
        included_sorted = sorted(included_values)
        low_latency_exceptions_by_platform[target_platform] = excluded_sorted
        low_latency_includes_by_platform[target_platform] = included_sorted
        set_low_latency_exceptions(excluded_sorted, platform=target_platform)
        set_low_latency_includes(included_sorted, platform=target_platform)
        settings_card.set_low_latency_rules(target_platform, excluded_sorted, included_sorted)

    def on_set_low_latency_item_mode(platform: str, value: str, mode: str):
        target_platform = (platform or "").strip().lower()
        normalized = (value or "").strip().lower()
        selected_mode = (mode or "").strip().lower()
        if target_platform not in {"windows", "linux"} or not normalized:
            return
        if selected_mode not in {"exclude", "include"}:
            return

        excluded_values = set(low_latency_exceptions_by_platform.get(target_platform, []))
        included_values = set(low_latency_includes_by_platform.get(target_platform, []))
        excluded_values.discard(normalized)
        included_values.discard(normalized)

        if selected_mode == "exclude":
            excluded_values.add(normalized)
        else:
            included_values.add(normalized)

        excluded_sorted = sorted(excluded_values)
        included_sorted = sorted(included_values)
        low_latency_exceptions_by_platform[target_platform] = excluded_sorted
        low_latency_includes_by_platform[target_platform] = included_sorted
        set_low_latency_exceptions(excluded_sorted, platform=target_platform)
        set_low_latency_includes(included_sorted, platform=target_platform)
        settings_card.set_low_latency_rules(target_platform, excluded_sorted, included_sorted)

        last_state = controller_ref.get("last_monitor_state", {})
        apply_monitor_latency_policy(
            bool(last_state.get("is_fullscreen", False)),
            str(last_state.get("app_id", "")),
            source="manual",
        )

    def on_add_low_latency_include_item(platform: str, value: str):
        on_add_low_latency_list_item(platform, value)
        on_set_low_latency_item_mode(platform, value, "include")

    def on_wait_until_app_close_change(e):
        enabled = bool(e.control.value)
        set_hold_until_app_close_enabled(enabled)
        update_status(
            f"Wait until app closes {'enabled' if enabled else 'disabled'}",
            "green" if enabled else "white",
        )
        page.update()

    settings_card = SettingsCard(
        on_low_latency_mode_change=on_latency_mode_change,
        on_add_low_latency_list_item=on_add_low_latency_list_item,
        on_remove_low_latency_list_item=on_remove_low_latency_list_item,
        on_set_low_latency_item_mode=on_set_low_latency_item_mode,
        on_add_low_latency_include_item=on_add_low_latency_include_item,
        on_wait_until_app_close_change=on_wait_until_app_close_change,
        on_check_battery=lambda _: controller.request_battery(),
        on_startup_toggle=on_startup_change,
        startup_enabled=is_startup_enabled(),
        low_latency_mode=controller_ref["selected_mode"],
        active_platform=platform_key,
        low_latency_exclusions_by_platform={
            "windows": sorted(low_latency_exceptions_by_platform.get("windows", [])),
            "linux": sorted(low_latency_exceptions_by_platform.get("linux", [])),
        },
        low_latency_inclusions_by_platform={
            "windows": sorted(low_latency_includes_by_platform.get("windows", [])),
            "linux": sorted(low_latency_includes_by_platform.get("linux", [])),
        },
        wait_until_app_close_enabled=controller_ref["hold_until_app_close_enabled"],
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Build Page Layout
    # ─────────────────────────────────────────────────────────────────────────
    page.add(
        title,
        Spacer(height=8),
        device_status_card,
        Spacer(height=10),
        settings_card,
        Spacer(height=5),
        Footer(APP_VERSION, GITHUB_URL),
        Spacer(height=10)
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Update Checker
    # ─────────────────────────────────────────────────────────────────────────
    def perform_update_check():
        """Check for updates and notify if available."""
        # Wait a bit for the UI to be fully ready
        time.sleep(3)
        has_update, latest_ver = check_for_updates()
        if has_update and latest_ver and should_show_update_notification(latest_ver):
            page.pubsub.send_all({"type": "update_notification", "latest_ver": latest_ver})

    threading.Thread(target=perform_update_check, daemon=True).start()

    def on_fullscreen_change(is_fullscreen: bool, app_id: str):
        page.pubsub.send_all(
            {"type": "fullscreen_state", "is_fullscreen": is_fullscreen, "app_id": app_id}
        )

    game_monitor = FullscreenGameMonitor(
        on_fullscreen_change=on_fullscreen_change,
        on_log=lambda msg: page.pubsub.send_all({"type": "status", "text": msg, "color": "orange"})
    )
    controller_ref["game_monitor"] = game_monitor
    game_monitor.start()

    # ─────────────────────────────────────────────────────────────────────────
    # Start Bluetooth Listener
    # ─────────────────────────────────────────────────────────────────────────
    threading.Thread(target=controller.listen, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    # Start Single Instance Listener
    # ─────────────────────────────────────────────────────────────────────────
    start_instance_listener(window_mgr)


if __name__ == "__main__":
    check_for_existing_instance()
    ft.app(target=main, assets_dir="assets")
