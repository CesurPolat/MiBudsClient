"""Mi Buds Client - Main Application Entry Point."""

import flet as ft
import os
import threading

from controllers.bluetooth import BTController
from utils.app.single_instance import (
    check_for_existing_instance,
    start_instance_listener,
    reserve_instance_port,
    release_instance_port,
)
from utils.app.updater import start_update_check
from ui import (
    APP_TITLE, COLOR_BG,
    WindowManager, SystemTray
)
from ui.components import (
    AppLayout, DeviceStatusCard
)
from controllers.device import DeviceConnection
from controllers.device.catalog_sync import CatalogSync
from ui.constants import APP_VERSION, PAGE_PADDING
from controllers.settings import SettingsController
from ui.app_message_handler import AppMessageHandler
from utils.diagnostics.debug_console import DebugConsoleManager
from utils.desktop.game_monitor import FullscreenGameMonitor
from controllers.latency import LatencyController
from utils.app.i18n import is_rtl, set_language
from utils.app.user_preferences import get_language_preference
from ui.page_updates import refresh_page
from utils.diagnostics.error_reports import ErrorReportManager, ReportQueue, guard_ui_callbacks
from utils.app.pubsub_topics import PubSubTopic
from ui.components.dialogs.error_report import ErrorReportDialog, ErrorReportEvents
from ui.components.dialogs.debug_console import DebugConsoleDialog
from utils.app.app_shutdown import ApplicationShutdown
from utils.desktop.linux_desktop import setup_linux_desktop

application_shutdown = ApplicationShutdown()

# Temporary manual QA switch: show the report form on every application launch.
SHOW_STARTUP_TEST_ERROR = False

async def main(page: ft.Page):
    """Main application entry point."""
    set_language(get_language_preference())
    page.rtl = is_rtl()

    ui_lock = threading.RLock()
    message_handler = None

    def publish(message):
        if not application_shutdown.started.is_set():
            page.pubsub.send_all(message)

    def update_ui():
        with ui_lock:
            if application_shutdown.started.is_set():
                return
            sync_tray = message_handler.sync_tray if message_handler is not None else None
            refresh_page(page, window_mgr, sync_tray=sync_tray)

    debug_console = DebugConsoleManager(publish=publish)
    debug_console.install()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Page Configuration
    # ─────────────────────────────────────────────────────────────────────────
    page.title = APP_TITLE
    page.bgcolor = COLOR_BG
    page.padding = PAGE_PADDING
    page.theme = ft.Theme(surfaces=ft.ThemeSurfaces.TONAL)
    page.dark_theme = ft.Theme(surfaces=ft.ThemeSurfaces.TONAL)
    
    # Newer Flet API properties
    page.window.icon = "icon.ico" if page.platform == ft.PagePlatform.WINDOWS else "icon.png"  # Path relative to assets_dir
    
    page.scroll = "auto"
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    window_mgr = WindowManager(page, auto_resize=True, on_shutdown=application_shutdown.stop)
    update_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # Initialize Managers
    # ─────────────────────────────────────────────────────────────────────────
    
    controller: BTController | None = None
    report_queue = ReportQueue(
        notify=lambda state: publish({'type': PubSubTopic.ERROR_REPORT_STATUS.value, 'state': state}),
        on_report_status=lambda status: publish({'type': PubSubTopic.CONNECTION_REPORT_STATUS.value, **status}),
    )
    reports = ErrorReportManager(
        publish=publish, app_version=APP_VERSION,
        get_device=lambda: (getattr(controller, 'diagnostic_identity', None) or {}).get('device_name', ''),
        auto_submit=report_queue.enqueue,
        get_identity=lambda: getattr(controller, 'diagnostic_identity', None),
    )
    application_shutdown.register("F12 listener", debug_console.stop_f12_hotkey_listener)
    application_shutdown.register("error reports", report_queue.stop)
    report_dialog = ErrorReportDialog(page, report_queue, ui_lock=ui_lock)
    debug_console.on_exception = reports.capture
    page.on_error = lambda e: reports.capture(RuntimeError(str(getattr(e, 'data', '') or 'Flet error').splitlines()[0]), 'ui')

    tray: SystemTray | None = None

    latency = LatencyController(
        publish=publish,
        get_controller=lambda: controller,
        get_tray=lambda: tray,
        on_rules_change=lambda *args: settings_card.set_low_latency_rules(*args),
        on_ui_update=update_ui,
    )
    application_shutdown.register("latency watcher", latency.stop)

    def tray_exit_request() -> None:
        publish({"type": PubSubTopic.APP.value, "action": "close"})

    tray = SystemTray(
        on_show=window_mgr.show,
        on_exit=tray_exit_request,
        on_latency_mode_select=latency.select_latency_mode_from_tray,
        get_latency_mode=lambda: latency.state["selected_mode"],
        latency_available=lambda: controller is not None and controller.capabilities.supports("latency"),
        on_device_action=publish,
    )
    window_mgr.tray_available = lambda: tray.available
    application_shutdown.register("system tray", tray.stop)

    # ─────────────────────────────────────────────────────────────────────────
    # Create UI Components
    # ─────────────────────────────────────────────────────────────────────────
    device_status_card = DeviceStatusCard()

    # ─────────────────────────────────────────────────────────────────────────
    # Controller Callbacks
    # ─────────────────────────────────────────────────────────────────────────
    device_connection = DeviceConnection(
        publish=publish,
        get_controller=lambda: controller,
    )
    application_shutdown.register("device requests", device_connection.stop)

    page.on_keyboard_event = debug_console.handle_keyboard_event
    if page.platform == ft.PagePlatform.LINUX:
        debug_dialog = DebugConsoleDialog(page, debug_console, ui_lock=ui_lock)
        debug_console.set_ui_console(debug_dialog.toggle)
        application_shutdown.register("debug console", debug_dialog.stop)
    catalog_sync = CatalogSync(
        publish=publish,
        get_identity=lambda: controller.device_identity if controller is not None else None,
        get_device_name=lambda: controller.device_name if controller is not None else "",
        app_version=APP_VERSION,
    )
    application_shutdown.register("catalog sync", catalog_sync.stop)
    cached_name, cached_image = catalog_sync.cached_device
    tray.set_device(cached_name, cached_image)
    if cached_image:
        device_status_card.update_catalog_device(cached_name, cached_image)

    # ─────────────────────────────────────────────────────────────────────────
    # Initialize Bluetooth Controller
    # ─────────────────────────────────────────────────────────────────────────
    def on_connection_event(event):
        publish({"type": PubSubTopic.CONNECTION_EVENT.value, "event": event})
        catalog_sync.identity_changed(None)
        if event == "connected" and controller is not None:
            threading.Thread(target=controller.request_device_identity, kwargs={"reconnect": False}, daemon=True).start()

    def on_identity(identity):
        catalog_sync.identity_changed(identity)
        publish({"type": PubSubTopic.FIRMWARE_INFO.value, "identity": identity})

    controller = BTController(
        error_callback=reports.capture,
        identity_callback=on_identity,
        connection_state_callback=lambda state, reason: publish(
            {"type": PubSubTopic.CONNECTION_STATE.value, "state": state, "reason": reason}
        ),
        status_callback=device_connection.update_status,
        battery_callback=device_connection.update_battery,
        check_battery_callback=device_connection.request_battery_delayed,
        connection_event_callback=on_connection_event,
    )
    
    controller.config_callback = lambda session, records, eq: publish(
        {"type": PubSubTopic.CONFIG_NOTIFICATION.value, "session": session, "records": records, "eq": eq})
    controller.device_candidates_callback = lambda devices: publish(
        {"type": PubSubTopic.DEVICE_CANDIDATES.value, "devices": [(item.name, item.address) for item in devices]})
    window_mgr.on_activity_change = controller.set_battery_polling_active
    controller.set_battery_polling_active(bool(
        page.window.visible and not page.window.minimized and getattr(page.window, "focused", False)
    ))
    application_shutdown.register("Bluetooth", controller.stop)

    # ─────────────────────────────────────────────────────────────────────────
    # Build Settings Card with Controller Actions
    # ─────────────────────────────────────────────────────────────────────────
    settings_controller = SettingsController(
        controller=controller,
        latency=latency,
        device_connection=device_connection,
        publish=publish,
        on_update=update_ui,
        on_language_change=lambda e: publish(
            {"type": PubSubTopic.LANGUAGE.value, "language": e.control.value}
        ),
    )
    settings_card = settings_controller.card
    settings_card.connection_panel.device_selector.on_select = lambda event: threading.Thread(
        target=controller.select_device, args=(event.control.value,), daemon=True).start()
    settings_card.set_catalog_device(cached_name, cached_image)
    settings_card.connection_panel.retry_button.on_click = lambda e: settings_card.retry_connection(
        device_connection.reconnect_on_show)

    # ─────────────────────────────────────────────────────────────────────────
    # Build Page Layout
    # ─────────────────────────────────────────────────────────────────────────
    layout = AppLayout(device_status_card, settings_card, on_update=update_ui,
                       viewport_width=page.width,
                       on_settings_change=window_mgr.set_settings_open)
    async def on_page_resize(_):
        if layout.set_viewport_width(page.width):
            update_ui()
        if layout.fit_settings_height():
            page.update()
    page.on_resize = on_page_resize
    content_measurement = ft.Screenshot(content=layout)
    page.add(content_measurement)
    window_mgr.set_content_measurement(content_measurement)
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
        on_catalog_stop=catalog_sync.stop,
        get_capabilities=lambda: controller.capabilities,
        get_identity=lambda: controller.device_identity if controller.connected else None,
        get_device_session=lambda: controller.eq_session,
        is_connected=lambda: controller.connected,
        report_events=ErrorReportEvents(dialog=report_dialog, reports=reports, queue=report_queue),
    )
    message_handler.sync_tray()
    application_shutdown.register("UI notifications", message_handler.begin_shutdown)
    page.pubsub.subscribe(message_handler.handle_on_ui_loop)
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
        on_update_available=lambda version: publish(
            {"type": PubSubTopic.UPDATE_NOTIFICATION.value, "latest_ver": version}
        )
    )

    def on_fullscreen_change(is_fullscreen: bool, app_id: str):
        publish(
            {"type": PubSubTopic.FULLSCREEN_STATE.value, "is_fullscreen": is_fullscreen, "app_id": app_id}
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Monitor fullscreen apps for automatic latency mode and forward logs to the UI.
    # ─────────────────────────────────────────────────────────────────────────
    game_monitor = FullscreenGameMonitor(
        on_fullscreen_change=on_fullscreen_change,
        on_log=lambda msg: publish({"type": PubSubTopic.STATUS.value, "text": msg, "color": "orange"})
    )
    application_shutdown.register("game monitor", game_monitor.stop)
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
        application_shutdown.register("Linux desktop identity", setup_linux_desktop())
        ft.run(main, assets_dir="assets")
    finally:
        try:
            application_shutdown.stop()
        finally:
            release_instance_port()
