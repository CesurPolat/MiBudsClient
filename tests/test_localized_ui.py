"""Live language changes preserve controls, pending requests, and user input."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import flet as ft
import msgpack
from flet.controls.base_control import BaseControl
from flet.messaging.protocol import configure_encode_object_for_msgpack

from controllers.bluetooth.gestures import GestureResult
from ui.app_message_handler import AppMessageHandler
from ui.components import AppLayout, DeviceStatusCard, SettingsCard
from ui.components.update_notification import show_update_notification
from ui.localization import refresh_translations
from ui.system_tray import SystemTray
from utils.i18n import get_language, message, set_language, t


class LocalizedUITests(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.preference_patch = patch("ui.components.settings_card.get_language_preference", return_value="system")
        self.preference_patch.start()
        self.addCleanup(self.preference_patch.stop)
        self.addCleanup(set_language, "en")
        self.assign = Mock()
        self.refresh = Mock()
        self.settings = SettingsCard(on_gesture_assignment=self.assign, on_gesture_refresh=self.refresh)
        self.device = DeviceStatusCard()
        self.layout = AppLayout(self.device, self.settings, Mock())
        self.page = SimpleNamespace(controls=[self.layout], overlay=[], update=Mock(), pubsub=Mock())
        self.tray = Mock()
        self.handler = AppMessageHandler(
            page=self.page, device_status_card=self.device, settings_card=self.settings,
            window_manager=Mock(), latency=Mock(), tray=self.tray, debug_console=Mock(),
            on_window_show=Mock(), get_game_monitor=Mock(),
        )

    def switch(self, language):
        with patch("ui.app_message_handler.set_language_preference") as save:
            self.handler.handle({"type": "language", "language": language})
        save.assert_called_once_with(language)

    def test_change_preserves_navigation_user_input_and_pending_gesture(self):
        self.layout.show_settings(True)
        self.settings.update_connection_state("connected")
        self.settings.auto_settings._field.value = "my-game.exe"
        self.settings.auto_settings.expanded = True
        self.settings.startup_switch.value = True
        panel = self.settings.gestures
        panel._opened = True
        panel.body.visible = True
        token = panel.begin(message("gesture.reading"))
        self.device.update_battery(128 + 67, 42, 90)
        controls = (self.layout.settings_content, self.settings.auto_settings._field, panel.body)
        self.switch("tr")
        self.assertEqual(self.layout.title.value, "Ayarlar")
        self.assertEqual(self.settings.startup_item.title.value, "Başlangıçta Çalıştır")
        self.assertEqual(self.device.battery_panel._left._label_text.value, "SOL")
        self.assertEqual(self.device.battery_panel._left._value_text.value, "⚡ %67")
        self.assertEqual(panel.status.value, "Hareket ayarları okunuyor...")
        self.assertEqual(panel._token, token)
        self.assertTrue(panel._busy)
        self.assertTrue(panel.body.visible)
        self.assertTrue(self.settings.startup_switch.value)
        self.assertTrue(self.settings.auto_settings.expanded)
        self.assertEqual(self.settings.auto_settings._field.value, "my-game.exe")
        self.assertEqual(controls, (self.layout.settings_content, self.settings.auto_settings._field, panel.body))
        self.refresh.assert_not_called()
        self.assign.assert_not_called()
        self.tray.refresh_menu.assert_called_once_with()
        panel.complete(token, GestureResult(True, {1: (1, 2)}, message("gesture.loaded")), {1: (1, 2)})
        self.assertEqual(panel.status.value, "Hareket ayarları yüklendi.")
        selector = panel.selectors[(1, "left")]
        callback = selector.on_select
        self.switch("zh-CN")
        self.assertEqual(panel.status.value, "触控设置已加载。")
        self.assertEqual(selector.label, "左耳")
        self.assertEqual(selector.options[0].text, "播放 / 暂停")
        self.assertIs(selector, panel.selectors[(1, "left")])
        self.assertIs(callback, selector.on_select)
        self.switch("en")
        self.assertEqual(selector.label, "Left")
        self.assertEqual(self.layout.title.value, "Settings")

    def test_failure_reason_status_identity_and_open_update_translate_in_place(self):
        reason = message("connection.technical", reason=message("connection.permission"), details="winerror 5")
        self.handler.handle({"type": "connection_state", "state": "failed", "reason": reason})
        self.handler.handle({"type": "status", "text": message("connection.retry_limit"), "color": "red"})
        self.handler.handle({"type": "device_identity", "text": message("identity.timeout")})
        show_update_notification(self.page, "v9.8.7")
        notice = self.page.overlay[0]
        checkbox = notice.content.controls[1].controls[0]
        checkbox.value = True
        self.switch("tr")
        self.assertEqual(self.settings.connection_panel.connection_label.value, "Bağlanılamadı")
        self.assertIn("Bluetooth erişimi reddedildi", self.settings.connection_panel.connection_reason.value)
        self.assertIn("winerror 5", self.settings.connection_panel.connection_reason.value)
        self.assertTrue(self.settings.connection_panel.retry_button.visible)
        self.assertFalse(self.settings.connected_controls.visible)
        self.assertEqual(self.device.status_bar.value, "Durum: Bağlanılamadı. Yeniden Dene'ye basın.")
        self.assertEqual(self.device.status_bar.color, "red")
        self.assertEqual(self.settings.identity_item.subtitle.value, "Cihaz kimliği sorgusu zaman aşımına uğradı.")
        self.assertIs(self.page.overlay[0], notice)
        self.assertTrue(notice.open)
        self.assertTrue(checkbox.value)
        self.assertEqual(notice.content.controls[0].value, "Yeni sürüm mevcut: v9.8.7")

    def test_raw_user_data_is_not_translated_and_message_strings_serialize(self):
        self.settings.auto_settings._field.value = "Settings"
        self.device.update_catalog_device("Redmi Buds 6 Play")
        self.switch("zh-CN")
        self.assertEqual(self.settings.auto_settings._field.value, "Settings")
        packed = msgpack.packb(self.layout, default=configure_encode_object_for_msgpack(BaseControl))
        decoded = msgpack.unpackb(packed)
        self.assertIn("设置", repr(decoded))
        self.assertIn("Redmi Buds 6 Play", repr(decoded))

    def test_new_components_use_selected_language_without_refresh(self):
        set_language("zh-CN")
        self.assertEqual(DeviceStatusCard().status_bar.value, "状态：正在启动…")
        self.assertEqual(SettingsCard().startup_item.title.value, "开机启动")

    def test_invalid_language_events_do_not_save_or_refresh(self):
        with patch("ui.app_message_handler.set_language_preference") as save:
            for value in (None, "de", [], {}):
                self.handler.handle({"type": "language", "language": value})
        save.assert_not_called()
        self.tray.refresh_menu.assert_not_called()
        self.assertEqual(get_language(), "en")

    def test_tray_menu_labels_and_notifications_follow_current_language(self):
        tray = SystemTray(Mock(), Mock())
        with patch("ui.system_tray.pystray.Icon") as icon:
            icon.HAS_MENU = True
            tray.run()
            menu = icon.call_args.args[3]
            self.assertEqual(menu.items[0].text, "Open")
            set_language("tr")
            tray.refresh_menu()
            self.assertEqual(menu.items[0].text, "Aç")
            self.assertEqual(menu.items[2].text, "Düşük Gecikme: Kapalı")
            tray.notify(message("tray.connected"))
            icon.return_value.notify.assert_called_once_with("Kulaklık bağlandı", "Mi Buds Client")


if __name__ == "__main__":
    unittest.main()
