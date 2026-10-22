"""Mi Buds Client - Main Application Entry Point."""

import flet as ft
import os
import threading

from bluetooth import BTController
from utils import (
    set_startup, 
    is_startup_enabled, 
    start_update_check,
    check_for_existing_instance,
    start_instance_listener
)
from ui import (
    APP_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, COLOR_BG,
    WindowManager, SystemTray
)
from ui.components import (
    AppLayout, DeviceStatusCard, SettingsCard
)
from ui.device_connection import DeviceConnection
from ui.app_message_handler import AppMessageHandler
from utils.debug_console import DebugConsoleManager
from utils.game_monitor import FullscreenGameMonitor
from utils.latency_controller import LatencyController

def main(page: ft.Page):
    """Main application entry point."""
    debug_console = DebugConsoleManager(publish=page.pubsub.send_all)
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
    device_status_card = DeviceStatusCard()

    # ─────────────────────────────────────────────────────────────────────────
    # Controller Callbacks
    # ─────────────────────────────────────────────────────────────────────────
    device_connection = DeviceConnection(
        publish=page.pubsub.send_all,
        get_controller=lambda: controller_ref["instance"],
    )

    page.on_keyboard_event = debug_console.handle_keyboard_event

    # ─────────────────────────────────────────────────────────────────────────
    # Initialize Bluetooth Controller
    # ─────────────────────────────────────────────────────────────────────────
    controller = BTController(
        status_callback=device_connection.update_status,
        battery_callback=device_connection.update_battery,
        check_battery_callback=device_connection.request_battery_delayed,
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
            device_connection.update_status(
                f"Startup {'enabled' if enabled else 'disabled'}", 
                "green" if enabled else "white"
            )
        else:
            device_connection.update_status("Failed to change startup setting", "red")
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
            device_connection.update_status(message, "green" if success else "red")

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
    layout = AppLayout(device_status_card, settings_card, on_update=page.update)
    page.add(layout)

    message_handler = AppMessageHandler(
        page=page,
        device_status_card=device_status_card,
        settings_card=settings_card,
        window_manager=window_mgr,
        latency=latency,
        tray=tray,
        debug_console=debug_console,
        on_window_show=device_connection.reconnect_on_show,
        get_game_monitor=lambda: controller_ref["game_monitor"],
    )
    page.pubsub.subscribe(message_handler.handle)
    threading.Thread(target=tray.run, daemon=True).start()
    debug_console.start_f12_hotkey_listener(debug_console.request_toggle)

    # ─────────────────────────────────────────────────────────────────────────
    # Update Checker
    # ─────────────────────────────────────────────────────────────────────────
    start_update_check(
        on_update_available=lambda version: page.pubsub.send_all(
            {"type": "update_notification", "latest_ver": version}
        )
    )

    def on_fullscreen_change(is_fullscreen: bool, app_id: str):
        page.pubsub.send_all(
            {"type": "fullscreen_state", "is_fullscreen": is_fullscreen, "app_id": app_id}
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Monitor fullscreen apps for automatic latency mode and forward logs to the UI.
    # ─────────────────────────────────────────────────────────────────────────
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
