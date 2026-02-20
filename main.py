"""Mi Buds Client - Main Application Entry Point."""

import flet as ft
import threading
import time

from bluetooth import BTController
from utils import (
    set_startup, 
    is_startup_enabled, 
    check_for_updates,
    check_for_existing_instance,
    start_instance_listener
)
from ui import (
    APP_TITLE, APP_VERSION, GITHUB_URL, WINDOW_WIDTH, WINDOW_HEIGHT, COLOR_BG, 
    BATTERY_UNKNOWN, WindowManager, SystemTray
)
from ui.components import (
    AppTitle, DeviceImage, BatteryPanel, SettingsCard, StatusBar, Spacer, Footer
)


def main(page: ft.Page):
    """Main application entry point."""
    
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
    page.window.resizable = False
    page.window.maximizable = False
    page.window.icon = "icon.ico"  # Path relative to assets_dir
    
    page.scroll = "auto"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # Initialize Managers
    # ─────────────────────────────────────────────────────────────────────────
    window_mgr = WindowManager(page)
    
    # Controller will be set after initialization
    controller_ref = {"instance": None, "low_latency": False}
    
    def toggle_latency_from_tray(new_state):
        controller_ref["low_latency"] = new_state
        if controller_ref["instance"]:
            mode = "low" if new_state else "std"
            controller_ref["instance"].send_command(mode)
        page.pubsub.send_all({"type": "latency", "enabled": new_state})

    tray = SystemTray(
        on_show=window_mgr.show,
        on_exit=window_mgr.close,
        on_latency_toggle=toggle_latency_from_tray,
        get_latency_state=lambda: controller_ref["low_latency"]
    )
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
            battery_panel.update_all(
                message.get("left", BATTERY_UNKNOWN),
                message.get("right", BATTERY_UNKNOWN),
                message.get("case", BATTERY_UNKNOWN)
            )
            page.update()
        
        elif msg_type == "window":
            action = message.get("action")
            if action == "show":
                window_mgr.apply_show()
            elif action == "hide":
                window_mgr.apply_hide()
        
        elif msg_type == "latency":
            enabled = message.get("enabled")
            settings_card.latency_switch.value = enabled
            update_status(
                f"{'Low Latency' if enabled else 'Standard'} mode set", 
                "blue" if enabled else "white"
            )
            page.update()

    page.pubsub.subscribe(on_pubsub_message)

    # ─────────────────────────────────────────────────────────────────────────
    # Controller Callbacks
    # ─────────────────────────────────────────────────────────────────────────
    def update_battery_ui(left, right, case):
        page.pubsub.send_all({
            "type": "battery", 
            "left": left, 
            "right": right, 
            "case": case
        })

    def update_status(text, color="white"):
        page.pubsub.send_all({
            "type": "status", 
            "text": text, 
            "color": color
        })

    def request_battery_delayed():
        time.sleep(1)
        controller.request_battery()

    # ─────────────────────────────────────────────────────────────────────────
    # Initialize Bluetooth Controller
    # ─────────────────────────────────────────────────────────────────────────
    controller = BTController(
        status_callback=update_status,
        battery_callback=update_battery_ui,
        check_battery_callback=lambda: threading.Thread(
            target=request_battery_delayed, 
            daemon=True
        ).start()
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
        enabled = e.control.value
        controller_ref["low_latency"] = enabled
        if controller:
            mode = "low" if enabled else "std"
            controller.send_command(mode)
            update_status(
                f"{'Low Latency' if enabled else 'Standard'} mode set", 
                "blue" if enabled else "white"
            )

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
        if has_update:
            def on_update_click(e):
                page.launch_url(GITHUB_URL)
                page.snack_bar.open = False
                page.update()

            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"New version available: {latest_ver}"),
                action="Download",
                on_action=on_update_click,
                duration=10000,
            )
            page.snack_bar.open = True
            page.update()

    threading.Thread(target=perform_update_check, daemon=True).start()

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
