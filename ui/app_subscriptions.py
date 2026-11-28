"""Connect UI event handlers to Flet PubSub topics."""

from .app_events import AppEvents
from .battery_notifications import BatteryNotifications
from .device_events import DeviceEvents
from .latency_events import LatencyEvents
from .tray_device import TrayDeviceEvents


def subscribe_ui_topic(pubsub, topic, handler, *, ui_lock, is_closing):
    async def on_message(_topic, message):
        # Flet runs async subscribers on its event loop.
        with ui_lock:
            if not is_closing() and isinstance(message, dict):
                handler(message)

    pubsub.subscribe_topic(topic.value, on_message)


def subscribe_ui_events(
    *, page, device_status_card, settings_card, window_manager, latency, tray, debug_console,
    on_window_show, publish, update_ui, ui_lock, shutdown, get_capabilities=None,
    get_identity=None, get_device_session=None, is_connected=None, report_events=None,
):
    """Bind application events and return the tray synchronization callback."""
    pubsub = page.pubsub
    closing = False
    notifications = BatteryNotifications(
        publish=publish, notify=tray.notify, on_disconnect=latency.clear_latency_hold,
    )

    def is_closing():
        return closing or shutdown.started.is_set()

    def begin_shutdown():
        nonlocal closing
        if closing:
            return
        closing = True
        notifications.stop()
        pubsub.unsubscribe_all()

    def set_single_body(single_body):
        device_status_card.battery_panel.set_single_body(single_body)
        notifications.set_single_body(single_body)

    tray_events = TrayDeviceEvents(
        tray=tray, settings=settings_card, latency=latency, get_capabilities=get_capabilities,
        get_session=get_device_session, is_connected=is_connected, set_single_body=set_single_body,
    )

    def sync_tray():
        if not is_closing():
            tray_events.sync()

    latency_events = LatencyEvents(
        latency=latency, settings=settings_card, publish=publish, update_page=update_ui,
    )
    device_events = DeviceEvents(
        settings=settings_card, status_card=device_status_card, latency=latency, tray=tray,
        notifications=notifications, tray_device=tray_events, get_capabilities=get_capabilities,
        get_identity=get_identity, get_session=get_device_session, is_connected=is_connected,
        sync_tray=sync_tray, refresh_latency=latency_events.refresh, update_page=update_ui,
    )
    app_events = AppEvents(
        page=page, settings=settings_card, status_card=device_status_card, tray=tray,
        window_manager=window_manager, debug_console=debug_console, on_window_show=on_window_show,
        report_events=report_events, begin_shutdown=begin_shutdown, update_page=update_ui,
    )
    sources = (app_events, device_events, latency_events, notifications, tray_events)
    if report_events is not None:
        sources += (report_events,)

    sync_tray()
    for source in sources:
        for topic, handler in source.topic_handlers().items():
            subscribe_ui_topic(pubsub, topic, handler, ui_lock=ui_lock, is_closing=is_closing)
    shutdown.register("UI subscriptions", begin_shutdown)
    return sync_tray
