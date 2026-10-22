"""Mi Buds Client - Main Application Entry Point."""

import flet as ft
import os
import sys
import threading
import time

from bluetooth import BTController
from utils import (
    set_startup, 
    is_startup_enabled, 
    check_for_updates,
    should_show_update_notification,
    check_for_existing_instance,
    start_instance_listener
)
from ui import (
    APP_TITLE, APP_VERSION, GITHUB_URL, WINDOW_WIDTH, WINDOW_HEIGHT, COLOR_BG, COLOR_CARD_BG,
    WindowManager, SystemTray
)
from ui.components import (
    AppTitle, DeviceStatusCard, SettingsCard, Spacer, Footer
)
from ui.battery_updates import BatteryUpdates
from ui.app_message_handler import AppMessageHandler
from utils.debug_console import DebugConsoleManager
from utils.game_monitor import FullscreenGameMonitor
from utils.latency_controller import LatencyController

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
        "reconnect_in_progress": False,
        "game_monitor": None,
    }

    tray_ref = {
        "instance": None
    }

    latency = LatencyController(
        publish=page.pubsub.send_all,
        get_controller=lambda: controller_ref["instance"],
        get_tray=lambda: tray_ref["instance"],
        on_rules_change=lambda *args: settings_card.set_low_latency_rules(*args),
        on_ui_update=page.update,
    )

    def tray_exit_request() -> None:
        page.pubsub.send_all({"type": "app", "action": "close"})

    tray = SystemTray(
        on_show=window_mgr.show,
        on_exit=tray_exit_request,
        on_latency_mode_select=latency.select_latency_mode_from_tray,
        get_latency_mode=lambda: latency.state["selected_mode"],
    )
    tray_ref["instance"] = tray

    # ─────────────────────────────────────────────────────────────────────────
    # Create UI Components
    # ─────────────────────────────────────────────────────────────────────────
    title = AppTitle(APP_TITLE)
    device_status_card = DeviceStatusCard()

    # ─────────────────────────────────────────────────────────────────────────
    # Controller Callbacks
    # ─────────────────────────────────────────────────────────────────────────
    battery_updates = BatteryUpdates(page.pubsub.send_all)

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

    # ─────────────────────────────────────────────────────────────────────────
    # Initialize Bluetooth Controller
    # ─────────────────────────────────────────────────────────────────────────
    controller = BTController(
        status_callback=update_status,
        battery_callback=battery_updates.update,
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

    def on_check_device_identity(e):
        if settings_card.identity_item.disabled:
            return
        settings_card.set_device_identity_result("Reading device identity...", pending=True)
        page.update()

        def query_identity():
            try:
                success, message = controller.request_device_identity()
            except Exception as exc:
                success, message = False, f"Device identity request failed: {exc}"
            page.pubsub.send_all({"type": "device_identity", "text": message})
            update_status(message, "green" if success else "red")

        threading.Thread(target=query_identity, daemon=True).start()

    settings_card = SettingsCard(
        on_check_device_identity=on_check_device_identity,
        on_low_latency_mode_change=latency.on_latency_mode_change,
        on_add_low_latency_list_item=latency.on_add_low_latency_list_item,
        on_remove_low_latency_list_item=latency.on_remove_low_latency_list_item,
        on_set_low_latency_item_mode=latency.on_set_low_latency_item_mode,
        on_add_low_latency_include_item=latency.on_add_low_latency_include_item,
        on_wait_until_app_close_change=latency.on_wait_until_app_close_change,
        on_check_battery=lambda _: controller.request_battery(),
        on_startup_toggle=on_startup_change,
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

    # ─────────────────────────────────────────────────────────────────────────
    # Build Page Layout
    # ─────────────────────────────────────────────────────────────────────────
    # Keep both pages mounted so background callbacks and form state survive navigation.
    transition = ft.Animation(220, ft.AnimationCurve.EASE_OUT_CUBIC)
    home_content = ft.Container(
        content=ft.Column(
            controls=[device_status_card, settings_card.home_controls_card],
            spacing=16,
        ),
        opacity=1,
        offset=ft.Offset(0, 0),
        animate_opacity=transition,
        animate_offset=transition,
    )
    settings_content = ft.Container(
        content=settings_card,
        opacity=0,
        offset=ft.Offset(0.06, 0),
        ignore_interactions=True,
        animate_opacity=transition,
        animate_offset=transition,
    )
    page_content = ft.Stack(
        controls=[home_content, settings_content],
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )

    def show_settings(open_settings: bool) -> None:
        home_content.opacity = 0 if open_settings else 1
        home_content.offset = ft.Offset(-0.06 if open_settings else 0, 0)
        home_content.ignore_interactions = open_settings
        settings_content.opacity = 1 if open_settings else 0
        settings_content.offset = ft.Offset(0 if open_settings else 0.06, 0)
        settings_content.ignore_interactions = not open_settings
        back_button.visible = open_settings
        settings_button.visible = not open_settings
        title.value = "Settings" if open_settings else APP_TITLE
        page.update()

    back_button = ft.IconButton(
        icon=ft.Icons.ARROW_BACK,
        icon_color="white",
        tooltip="Back",
        visible=False,
        on_click=lambda _: show_settings(False),
    )
    settings_button = ft.IconButton(
        icon=ft.Icons.SETTINGS_OUTLINED,
        icon_color="white",
        tooltip="Settings",
        on_click=lambda _: show_settings(True),
    )
    navigation_header = ft.Row(
        controls=[
            ft.Container(content=back_button, width=48),
            ft.Container(content=title, expand=True, alignment=ft.Alignment.CENTER),
            ft.Container(content=settings_button, width=48),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    page.add(
        navigation_header,
        Spacer(height=8),
        page_content,
        Spacer(height=5),
        Footer(APP_VERSION, GITHUB_URL),
        Spacer(height=10)
    )

    message_handler = AppMessageHandler(
        page=page,
        device_status_card=device_status_card,
        settings_card=settings_card,
        window_manager=window_mgr,
        latency=latency,
        tray=tray,
        debug_console=debug_console,
        on_window_show=reconnect_if_disconnected_on_show,
        get_game_monitor=lambda: controller_ref["game_monitor"],
    )
    page.pubsub.subscribe(message_handler.handle)
    threading.Thread(target=tray.run, daemon=True).start()
    debug_console.start_f12_hotkey_listener(
        lambda: page.pubsub.send_all({"type": "debug_console", "action": "toggle"})
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
