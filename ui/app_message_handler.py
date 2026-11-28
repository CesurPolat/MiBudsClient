"""Dispatch application topics on Flet's UI loop."""

import threading
from typing import Callable

from .app_events import AppEvents
from .battery_notifications import BatteryNotifications
from .device_events import DeviceEvents
from .latency_events import LatencyEvents
from .page_updates import refresh_page
from .tray_device import TrayDeviceEvents


class AppMessageHandler:
    """Wire topic handlers and serialize UI updates."""

    def __init__(self, *, page, device_status_card, settings_card, window_manager,
                 latency, tray, debug_console, on_window_show: Callable,
                 on_catalog_stop: Callable | None = None,
                 get_capabilities: Callable | None = None, ui_lock=None,
                 get_identity: Callable | None = None, get_device_session: Callable | None = None,
                 is_connected: Callable | None = None, report_events=None):
        self._dispatch_lock = ui_lock if ui_lock is not None else threading.RLock()
        self._closing = False
        self._page = page
        self._window_manager = window_manager
        self._notifications = BatteryNotifications(
            publish=self._publish, notify=tray.notify, on_disconnect=latency.clear_latency_hold,
        )

        def set_single_body(single_body):
            device_status_card.battery_panel.set_single_body(single_body)
            self._notifications.set_single_body(single_body)

        self._tray_device = TrayDeviceEvents(
            tray=tray, settings=settings_card, latency=latency, get_capabilities=get_capabilities,
            get_session=get_device_session, is_connected=is_connected, set_single_body=set_single_body,
        )
        latency_events = LatencyEvents(
            latency=latency, settings=settings_card, publish=self._publish, update_page=self._update_page,
        )
        self._device_events = DeviceEvents(
            settings=settings_card, status_card=device_status_card, latency=latency, tray=tray,
            notifications=self._notifications, tray_device=self._tray_device, get_capabilities=get_capabilities,
            get_identity=get_identity, get_session=get_device_session, is_connected=is_connected,
            sync_tray=self.sync_tray, refresh_latency=latency_events.refresh, update_page=self._update_page,
        )
        app_events = AppEvents(
            page=page, settings=settings_card, status_card=device_status_card, tray=tray,
            window_manager=window_manager, debug_console=debug_console, on_window_show=on_window_show,
            report_events=report_events, begin_shutdown=self.begin_shutdown,
            update_page=self._update_page,
        )
        self._routes = {
            **app_events.routes(),
            **self._device_events.routes(),
            **latency_events.routes(),
            **self._notifications.routes(),
            **self._tray_device.routes(),
        }
        if report_events is not None:
            self._routes.update(report_events.routes())

    def sync_tray(self):
        """Publish value-only snapshots from the serialized Flet update path."""
        if not self._closing:
            self._tray_device.sync()

    def _publish(self, message):
        self._page.pubsub.send_all(message)

    def _update_page(self) -> None:
        refresh_page(self._page, self._window_manager, sync_tray=self.sync_tray)

    async def handle_on_ui_loop(self, message) -> None:
        """Apply PubSub messages alongside native Flet events without yielding."""
        self.handle(message)

    def handle(self, message) -> None:
        """Serialize live PubSub and direct calls through the same route table."""
        with self._dispatch_lock:
            self._handle_message(message)

    def _handle_message(self, message) -> None:
        if self._closing or not isinstance(message, dict):
            return
        topic = message.get("type")
        if not isinstance(topic, str):
            return
        handler = self._routes.get(topic)
        if handler:
            handler(message)

    def begin_shutdown(self) -> None:
        """Discard late UI messages and cancel pending notifications."""
        self._closing = True
        self._notifications.stop()
