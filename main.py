"""Mi Buds Client - Main Application Entry Point."""

import flet as ft
import threading
import time
import os

from bluetooth import BTController
from updater import check_for_updates
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
    
    page.scroll = "auto"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # Initialize Managers
    # ─────────────────────────────────────────────────────────────────────────
    window_mgr = WindowManager(page)
    
    # Controller will be set after initialization
    controller_ref = {"instance": None}
    
    tray = SystemTray(
        on_show=window_mgr.show,
        on_exit=lambda: os._exit(0),
        on_low_latency=lambda: controller_ref["instance"] and controller_ref["instance"].send_command("low"),
        on_standard=lambda: controller_ref["instance"] and controller_ref["instance"].send_command("std")
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
    settings_card = SettingsCard(
        on_low_latency=lambda _: controller.send_command("low"),
        on_standard=lambda _: controller.send_command("std"),
        on_check_battery=lambda _: controller.request_battery()
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


if __name__ == "__main__":
    ft.run(main)
