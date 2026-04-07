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
    get_low_latency_exceptions,
    check_for_existing_instance,
    start_instance_listener
)
from ui import (
    APP_TITLE, APP_VERSION, GITHUB_URL, WINDOW_WIDTH, WINDOW_HEIGHT, COLOR_BG, 
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
        "low_latency": False,
        "reconnect_in_progress": False,
        "manual_override_until": 0.0,
        "auto_mode_active": False,
        "game_monitor": None
    }
    low_latency_exceptions = set(get_low_latency_exceptions())

    notification_state = {
        "last_connection_event": None
    }

    tray_ref = {
        "instance": None
    }

    debug_state = {
        "last_toggle_at": 0.0
    }

    def set_latency_mode(new_state: bool, source: str = "manual"):
        controller_ref["low_latency"] = new_state

        if source == "manual":
            controller_ref["manual_override_until"] = time.monotonic() + 45
            controller_ref["auto_mode_active"] = False
        elif source == "auto_on":
            controller_ref["auto_mode_active"] = True
        elif source == "auto_off":
            controller_ref["auto_mode_active"] = False

        if controller_ref["instance"]:
            mode = "low" if new_state else "std"
            success, message = controller_ref["instance"].send_command(mode)
            if not success:
                page.pubsub.send_all({"type": "status", "text": message, "color": "red"})

        tray_inst = tray_ref["instance"]
        if tray_inst:
            tray_inst.refresh_menu()

        page.pubsub.send_all({"type": "latency", "enabled": new_state})
    
    def toggle_latency_from_tray(new_state):
        set_latency_mode(bool(new_state), source="manual")

    def tray_exit_request() -> None:
        page.pubsub.send_all({"type": "app", "action": "close"})

    tray = SystemTray(
        on_show=window_mgr.show,
        on_exit=tray_exit_request,
        on_latency_toggle=toggle_latency_from_tray,
        get_latency_state=lambda: controller_ref["low_latency"]
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
            enabled = message.get("enabled")
            controller_ref["low_latency"] = bool(enabled)
            settings_card.latency_switch.value = enabled
            update_status(
                f"{'Low Latency' if enabled else 'Standard'} mode set", 
                "blue" if enabled else "white"
            )
            page.update()

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
                tray.notify("Earbuds disconnected")

        elif msg_type == "fullscreen_state":
            is_fullscreen = bool(message.get("is_fullscreen", False))
            app_id = str(message.get("app_id", "")).strip().lower()
            if time.monotonic() < controller_ref["manual_override_until"]:
                return

            if is_fullscreen and app_id and app_id in low_latency_exceptions:
                update_status(f"Auto low latency skipped for {app_id}", "orange")
                return

            if is_fullscreen and not controller_ref["low_latency"]:
                set_latency_mode(True, source="auto_on")
                update_status("Fullscreen detected. Low Latency enabled", "blue")
            elif not is_fullscreen and controller_ref["auto_mode_active"]:
                set_latency_mode(False, source="auto_off")
                update_status("Fullscreen ended. Standard mode restored", "white")

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

    def on_latency_toggle(e):
        enabled = bool(e.control.value)
        set_latency_mode(enabled, source="manual")

    settings_card = SettingsCard(
        on_low_latency_toggle=on_latency_toggle,
        on_check_battery=lambda _: controller.request_battery(),
        on_startup_toggle=on_startup_change,
        startup_enabled=is_startup_enabled(),
        low_latency_enabled=False # Default to standard on start
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Build Page Layout
    # ─────────────────────────────────────────────────────────────────────────
    page.add(
        title,
        Spacer(height=20),
        device_image,
        status_bar,
        Spacer(height=20),
        battery_panel,
        Spacer(height=20),
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
