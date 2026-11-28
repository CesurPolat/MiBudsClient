"""Apply device and device-setting topics to the UI."""

from datetime import datetime

import flet as ft

from controllers.battery.stream import BATTERY_UNKNOWN
from controllers.gestures.protocol import parse_gesture_records
from utils.app.pubsub_topics import PubSubTopic


class DeviceEvents:
    def __init__(self, *, settings, status_card, latency, tray, notifications, tray_device,
                 get_capabilities, get_identity, get_session, is_connected, sync_tray,
                 refresh_latency, update_page):
        self._settings = settings
        self._status_card = status_card
        self._latency = latency
        self._tray = tray
        self._notifications = notifications
        self._tray_device = tray_device
        self._get_capabilities = get_capabilities
        self._get_identity = get_identity
        self._get_session = get_session
        self._is_connected = is_connected
        self._sync_tray = sync_tray
        self._refresh_latency = refresh_latency
        self._update_page = update_page
        self._latest_report = float("-inf")
        self._report_state = None

    def routes(self):
        return {
            PubSubTopic.BATTERY.value: self.on_battery,
            PubSubTopic.STATUS.value: self.on_status,
            PubSubTopic.CONNECTION_STATE.value: self.on_connection_state,
            PubSubTopic.CONNECTION_REPORT_STATUS.value: self.on_report_status,
            PubSubTopic.DEVICE_CANDIDATES.value: self.on_candidates,
            PubSubTopic.CATALOG_DEVICE.value: self.on_catalog_device,
            PubSubTopic.CAPABILITIES_CHANGED.value: self.on_capabilities_changed,
            PubSubTopic.DEVICE_IDENTITY.value: self.on_identity,
            PubSubTopic.FIRMWARE_INFO.value: self.on_firmware,
            PubSubTopic.GESTURE_SETTINGS.value: self.on_gesture_settings,
            PubSubTopic.EQ_SETTINGS.value: self.on_eq_settings,
            PubSubTopic.NOISE_SETTINGS.value: self.on_noise_settings,
            PubSubTopic.NOISE_NOTIFICATION.value: self.on_noise_notification,
            PubSubTopic.CONFIG_NOTIFICATION.value: self.on_config_notification,
        }

    def on_battery(self, message):
        left = message.get("left", BATTERY_UNKNOWN)
        right = message.get("right", BATTERY_UNKNOWN)
        case = message.get("case", BATTERY_UNKNOWN)
        transient = message.get("transient", False)
        self._sync_tray()
        self._tray_device.on_battery(left, right, case, transient=transient)
        self._notifications.on_battery(left, right, case, transient=transient)
        self._status_card.update_battery(left, right, case, transient=transient)
        self._update_page()

    def on_status(self, message):
        self._status_card.update_status(message.get("text", ""), message.get("color", "white"))
        self._update_page()

    def on_connection_state(self, message):
        state, reason = message.get("state", ""), message.get("reason", "")
        self._refresh_capabilities()
        self._notifications.on_connection_state(state)
        self._settings.update_connection_state(state, reason)
        self._status_card.update_connection_state(state, reason)
        self._update_page()

    def on_report_status(self, message):
        if message.get("action") not in {"bluetooth_connect", "bluetooth_discovery", "bluetooth_receive"}:
            return
        state = message.get("state")
        if state not in {"queued", "sent", "failed"}:
            return
        try:
            occurred_at = datetime.fromisoformat(message.get("occurred_at", "").replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError, AttributeError):
            return
        if (occurred_at < self._latest_report
                or (occurred_at == self._latest_report and state == "queued"
                    and self._report_state in {"sent", "failed"})):
            return
        self._latest_report = occurred_at
        self._report_state = state
        self._settings.connection_panel.update_report_status(state)
        self._update_page()

    def on_candidates(self, message):
        devices = message["devices"]
        selector = self._settings.connection_panel.device_selector
        selector.options = [ft.DropdownOption(address, name) for name, address in devices]
        selector.visible = len(devices) > 1
        self._update_page()

    def on_catalog_device(self, message):
        name, image_path = message.get("name", ""), message.get("image_path", "")
        self._tray.set_device(name, image_path)
        self._settings.set_catalog_device(name, image_path)
        self._status_card.update_catalog_device(name, image_path)
        self._update_page()

    def on_capabilities_changed(self, message):
        self._refresh_capabilities()
        self._update_page()

    def _refresh_capabilities(self):
        if self._get_capabilities is not None:
            capabilities = self._get_capabilities()
            self._settings.set_capabilities(capabilities)
            self._latency.set_device_capabilities(capabilities)
            self._latency.refresh_device_state()
            self._tray.refresh_menu()

    def on_identity(self, message):
        self._settings.set_device_identity_result(message["text"])
        self._update_page()

    def on_firmware(self, message):
        identity = message.get("identity")
        if identity is not None and self._get_identity is not None and self._get_identity() is identity:
            self._settings.set_firmware_version(identity.firmware_version)
            self._refresh_capabilities()
            self._update_page()

    def on_gesture_settings(self, message):
        self._settings.gestures.complete(message["token"], message["result"], message["capabilities"])
        self._update_page()

    def on_eq_settings(self, message):
        self._settings.equalizer.complete(message["token"], message["result"], message["profiles"], message["operation"])
        self._settings.refresh_connection_panel()
        self._update_page()

    def on_noise_settings(self, message):
        self._settings.noise.complete(message["token"], message["state"], message.get("error"))
        self._update_page()

    def on_noise_notification(self, message):
        if self._get_session and message["session"] != self._get_session():
            return
        self._settings.noise.notification(message["session"], message["state"])
        self._update_page()

    def on_config_notification(self, message):
        if (self._get_session is None or message["session"] != self._get_session()
                or (self._is_connected and not self._is_connected())):
            return
        records = message["records"]
        if message.get("eq") is not None:
            self._settings.equalizer.notification(message["eq"])
        if 2 in records or 80 in records:
            config = 80 if 80 in records else 2
            value = records[config]
            try:
                assignments = parse_gesture_records(
                    bytes((len(value) + 2,)) + config.to_bytes(2, "big") + value, physical=True,
                )
            except ValueError:
                pass
            else:
                self._settings.gestures.notification(assignments)
        if 47 in records:
            self._refresh_latency()
        self._update_page()
