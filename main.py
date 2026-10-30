"""Mi Buds Client - Main Application Entry Point."""

import flet as ft
import os
import threading

from controllers.bluetooth import BTController
from utils import (
    start_update_check,
    check_for_existing_instance,
    start_instance_listener,
    reserve_instance_port,
    release_instance_port,
)
from ui import (
    APP_TITLE, COLOR_BG,
    WindowManager, SystemTray
)
from ui.components import (
    AppLayout, DeviceStatusCard
)
from controllers.device import DeviceConnection
from controllers.device.catalog_sync import CatalogSync
from ui.constants import APP_VERSION
from controllers.settings import SettingsController
from ui.app_message_handler import AppMessageHandler
from utils.debug_console import DebugConsoleManager
from utils.game_monitor import FullscreenGameMonitor
from controllers.latency import LatencyController
from utils.i18n import is_rtl, set_language
from utils.user_preferences import get_language_preference
from ui.localization import refresh_translations
from utils.error_reports import ErrorReportManager, ReportQueue, guard_ui_callbacks
from ui.components.error_report import ErrorReportDialog

# Temporary manual QA switch: show the report form on every application launch.
SHOW_STARTUP_TEST_ERROR = True

def main(page: ft.Page):
    """Main application entry point."""
    set_language(get_language_preference())
    page.rtl = is_rtl()

    ui_lock = threading.RLock()

    def update_ui():
        with ui_lock:
            refresh_translations(page.controls)
            refresh_translations(page.overlay)
            page.update()

    debug_console = DebugConsoleManager(publish=page.pubsub.send_all)
    debug_console.install()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Page Configuration
    # ─────────────────────────────────────────────────────────────────────────
    page.title = APP_TITLE
    page.bgcolor = COLOR_BG
    page.padding = 20
    
    # Newer Flet API properties
    page.window.icon = "icon.ico" if page.platform == ft.PagePlatform.WINDOWS else "icon.png"  # Path relative to assets_dir
    
    page.scroll = "auto"
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    window_mgr = WindowManager(page)
    update_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # Initialize Managers
    # ─────────────────────────────────────────────────────────────────────────
    
    # Controller will be set after initialization
    controller_ref = {
        "instance": None,
        "game_monitor": None,
    }
    reports = ErrorReportManager(
        publish=page.pubsub.send_all, app_version=APP_VERSION,
        get_device=lambda: getattr(getattr(controller_ref['instance'], 'capabilities', None), 'name', ''),
    )
    report_queue = ReportQueue(notify=lambda state: page.pubsub.send_all(
        {'type': 'error_report_status', 'state': state}))
    report_dialog = ErrorReportDialog(page, report_queue, ui_lock=ui_lock)
    debug_console.on_exception = reports.capture
    page.on_error = lambda e: reports.capture(RuntimeError(str(getattr(e, 'data', '') or 'Flet error').splitlines()[0]), 'ui')

    tray_ref = {
        "instance": None
    }

    latency = LatencyController(
        publish=page.pubsub.send_all,
        get_controller=lambda: controller_ref["instance"],
        get_tray=lambda: tray_ref["instance"],
        on_rules_change=lambda *args: settings_card.set_low_latency_rules(*args),
        on_ui_update=update_ui,
    )

    def tray_exit_request() -> None:
        page.pubsub.send_all({"type": "app", "action": "close"})

    tray = SystemTray(
        on_show=window_mgr.show,
        on_exit=tray_exit_request,
        on_latency_mode_select=latency.select_latency_mode_from_tray,
        get_latency_mode=lambda: latency.state["selected_mode"],
        latency_available=lambda: controller_ref["instance"] is not None and controller_ref["instance"].capabilities.supports("latency"),
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
    catalog_sync = CatalogSync(
        publish=page.pubsub.send_all,
        get_identity=lambda: controller_ref["instance"].device_identity
        if controller_ref["instance"] is not None else None,
        get_device_name=lambda: controller_ref["instance"].device_name
        if controller_ref["instance"] is not None else "",
        app_version=APP_VERSION,
    )
    cached_name, cached_image = catalog_sync.cached_device
    tray.set_device(cached_name, cached_image)
    if cached_image:
        device_status_card.update_catalog_device(cached_name, cached_image)

    # ─────────────────────────────────────────────────────────────────────────
    # Initialize Bluetooth Controller
    # ─────────────────────────────────────────────────────────────────────────
    def on_connection_event(event):
        page.pubsub.send_all({"type": "connection_event", "event": event})
        catalog_sync.identity_changed(None)

    controller = BTController(
        identity_callback=catalog_sync.identity_changed,
        connection_state_callback=lambda state, reason: page.pubsub.send_all(
            {"type": "connection_state", "state": state, "reason": reason}
        ),
        status_callback=device_connection.update_status,
        battery_callback=device_connection.update_battery,
        check_battery_callback=device_connection.request_battery_delayed,
        connection_event_callback=on_connection_event,
    )
    
    # Set controller reference for tray callbacks
    controller_ref["instance"] = controller

    # ─────────────────────────────────────────────────────────────────────────
    # Build Settings Card with Controller Actions
    # ─────────────────────────────────────────────────────────────────────────
    settings_controller = SettingsController(
        controller=controller,
        latency=latency,
        device_connection=device_connection,
        publish=page.pubsub.send_all,
        on_update=update_ui,
        on_language_change=lambda e: page.pubsub.send_all(
            {"type": "language", "language": e.control.value}
        ),
    )
    settings_card = settings_controller.card
    settings_card.connection_panel.retry_button.on_click = lambda e: device_connection.reconnect_on_show()

    # ─────────────────────────────────────────────────────────────────────────
    # Build Page Layout
    # ─────────────────────────────────────────────────────────────────────────
    layout = AppLayout(device_status_card, settings_card, on_update=update_ui)
    page.add(layout)
    guard_ui_callbacks(page.controls, reports.capture, ui_lock=ui_lock)

    message_handler = AppMessageHandler(
        ui_lock=ui_lock,
        page=page,
        device_status_card=device_status_card,
        settings_card=settings_card,
        window_manager=window_mgr,
        latency=latency,
        tray=tray,
        debug_console=debug_console,
        on_window_show=device_connection.reconnect_on_show,
        get_game_monitor=lambda: controller_ref["game_monitor"],
        on_catalog_stop=catalog_sync.stop,
        get_capabilities=lambda: controller.capabilities,
    )
    def handle_message(message):
        try:
            if isinstance(message, dict):
                kind = message.get('type')
                if kind == 'report_exception':
                    reports.capture(message['error'], message.get('action', ''))
                    return True
                if kind == 'error_report':
                    report_dialog.receive(message['report'])
                    return True
                if kind == 'error_report_status':
                    report_dialog.status(message['state'])
                    return True
                if kind == 'app' and message.get('action') == 'close':
                    report_queue.stop()
        except Exception as exc:
            if not isinstance(message, dict) or message.get('type') not in {'error_report', 'error_report_status', 'report_exception'}:
                reports.capture(exc, 'ui_message')
    message_handler.report_message = handle_message
    message_handler.report_on_show = report_dialog.show_pending
    page.pubsub.subscribe(message_handler.handle)
    if SHOW_STARTUP_TEST_ERROR:
        try:
            raise RuntimeError("Test error: application startup error report form")
        except RuntimeError as exc:
            reports.capture(exc, 'startup_test')
    report_queue.start()
    catalog_sync.start()
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
    reserve_instance_port()
    try:
        ft.app(target=main, assets_dir="assets")
    finally:
        release_instance_port()
