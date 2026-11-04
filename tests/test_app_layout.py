"""Screen navigation preserves component state and routes interactions correctly."""

import unittest
from unittest.mock import Mock

from ui.components import AppLayout, DeviceStatusCard, SettingsCard


class AppLayoutTests(unittest.TestCase):
    def test_navigation_keeps_controls_and_their_state(self):
        device = DeviceStatusCard()
        settings = SettingsCard(startup_enabled=True, low_latency_mode="auto")
        settings.set_device_identity_result("Redmi Buds 6 Play")
        device.update_battery(70, 80, 90)
        update = Mock()
        layout = AppLayout(device, settings, on_update=update)
        screens = list(layout.page_content.controls)
        mounted_slots = [control for control in layout.controls if control.visible]

        self.assertEqual(layout.home_content.offset.x, 0)
        self.assertTrue(layout.home_content.content.intrinsic_height)
        self.assertEqual(device.expand, 2)
        self.assertEqual(settings.home_controls_card.expand, 3)
        self.assertEqual(layout.settings_content.offset.x, 1)
        self.assertTrue(layout.settings_content.ignore_interactions)
        self.assertIs(layout.footer.controls[0].content, layout.navigation_button)
        self.assertEqual(layout.footer.controls[1].controls[1].value, "|")
        self.assertIsNone(layout.home_content.height)
        self.assertIsNone(layout.settings_content.height)
        self.assertEqual((layout.settings_content.top, layout.settings_content.bottom,
                          layout.settings_content.left, layout.settings_content.right), (0, 0, 0, 0))

        layout.navigation_button.on_click(None)
        self.assertEqual(
            [control for control in layout.controls if control.visible], mounted_slots)
        self.assertEqual(layout.navigation_button.content.value, "Back")
        self.assertEqual(layout.navigation_button.tooltip, "Back")
        self.assertTrue(layout.home_content.ignore_interactions)
        self.assertFalse(layout.settings_content.ignore_interactions)
        self.assertEqual(layout.home_content.offset.x, -1)
        self.assertEqual(layout.settings_content.offset.x, 0)
        self.assertTrue(layout.navigation_button.visible)
        self.assertIsNone(layout.home_content.height)
        self.assertIsNone(layout.settings_content.height)

        layout.navigation_button.on_click(None)
        self.assertEqual(
            [control for control in layout.controls if control.visible], mounted_slots)
        self.assertIsNone(layout.settings_content.height)
        self.assertEqual((layout.settings_content.top, layout.settings_content.bottom,
                          layout.settings_content.left, layout.settings_content.right), (0, 0, 0, 0))
        self.assertFalse(layout.home_content.ignore_interactions)
        self.assertTrue(layout.settings_content.ignore_interactions)
        self.assertEqual(layout.home_content.offset.x, 0)
        self.assertEqual(layout.settings_content.offset.x, 1)
        self.assertTrue(layout.navigation_button.visible)
        self.assertEqual(layout.navigation_button.content.value, "Settings")
        self.assertEqual(layout.page_content.controls, screens)
        self.assertEqual(layout.home_content.content.controls, [device, settings.home_controls_card])
        self.assertIs(layout.settings_content.content, settings)
        self.assertTrue(settings.startup_switch.value)
        self.assertEqual(settings.latency_item.value, "auto")
        self.assertEqual(settings.identity_item.subtitle.value, "Redmi Buds 6 Play")
        self.assertEqual(device.battery_panel._left._value_text.value, "%70")
        self.assertEqual(update.call_count, 2)

    def test_settings_sections_trigger_reads_and_fall_back_on_disconnect(self):
        from controllers.bluetooth.capabilities import resolve_capabilities
        gesture_read, eq_action = Mock(), Mock()
        settings = SettingsCard(on_gesture_refresh=gesture_read, on_eq_action=eq_action)
        settings.set_capabilities(resolve_capabilities("Redmi Buds 6 Play"))
        settings.update_connection_state("connected")
        self.assertEqual(settings._selected_section, "general")
        settings.select_section("gestures")
        self.assertTrue(settings.gestures.body.visible)
        gesture_read.assert_called_once()
        self.assertNotIn("eq", settings._sections)
        self.assertTrue(settings.equalizer.quick_controls.visible)
        settings.startup_switch.value = True
        settings.select_section("general")
        self.assertTrue(settings.startup_switch.value)
        settings.select_section("gestures")
        settings.update_connection_state("disconnected")
        self.assertEqual(settings._selected_section, "general")
        self.assertTrue(settings._sections["general"].visible)

    def test_settings_navigation_resize_keeps_selection_and_tooltips(self):
        from utils.i18n import set_language
        from ui.localization import refresh_translations
        settings = SettingsCard(startup_enabled=True)
        settings.select_section("identity")
        settings.set_viewport_width(420)
        self.assertEqual(settings._selected_section, "identity")
        self.assertEqual(settings._menu.width, 52)
        self.assertTrue(all(item.tooltip for item in settings._menu.controls))
        self.assertTrue(all(not item.content.controls[1].visible for item in settings._menu.controls))
        settings.set_viewport_width(650)
        self.assertEqual(settings._selected_section, "identity")
        self.assertTrue(settings.startup_switch.value)
        try:
            set_language("tr")
            refresh_translations(settings)
            self.assertEqual(settings._section_title.value, "Cihaz bilgisi")
            self.assertEqual(settings._menu.controls[0].tooltip, "Genel")
        finally:
            set_language("en")

    def test_all_settings_sections_share_one_card_surface(self):
        settings = SettingsCard()
        self.assertEqual(settings._section_surface.content.controls, list(settings._sections.values()))
        surface = settings._section_surface
        self.assertIsNotNone(surface.border)
        settings.select_section("identity")
        self.assertIs(settings._section_column.controls[1], surface)
        self.assertTrue(settings.identity_section.visible)
        self.assertFalse(settings._sections["general"].visible)

    def test_device_info_uses_connected_catalog_data_and_clears_on_disconnect(self):
        from controllers.bluetooth.capabilities import resolve_capabilities
        settings = SettingsCard()
        settings.set_capabilities(resolve_capabilities("Redmi Buds 6 Play"))
        settings.update_connection_state("connected")
        settings.set_catalog_device("Redmi Buds 6 Play", "assets/icon.png")
        settings.select_section("identity")
        self.assertTrue(settings.identity_image._image_control.src.endswith("icon.png"))
        self.assertEqual(settings.identity_firmware.value, "\u2014")
        self.assertNotIn(settings.identity_item, settings.identity_section.content.controls)
        self.assertIn("Redmi Buds 6 Play", settings.identity_name.value)
        self.assertIn("miwear.headphone.n79bg", settings.identity_model.value)
        settings.update_connection_state("disconnected")
        self.assertNotIn("Redmi Buds 6 Play", settings.identity_name.value)
        self.assertEqual(settings.identity_image._image_control.src, "")

    def test_resize_preserves_controls_and_moves_battery_to_bottom_only_when_wide(self):
        device = DeviceStatusCard()
        settings = SettingsCard()
        layout = AppLayout(device, settings, on_update=Mock(), viewport_width=1100)
        self.assertTrue(device._battery_spacer.visible)
        self.assertFalse(device.content.tight)
        self.assertTrue(layout.set_viewport_width(480))
        self.assertFalse(device._battery_spacer.visible)
        self.assertTrue(device.content.tight)
        self.assertEqual(layout.home_content.content.controls, [device, settings.home_controls_card])
        self.assertTrue(settings._compact_navigation)
        self.assertEqual(settings._menu.width, 52)
        self.assertTrue(layout.set_viewport_width(500))
        self.assertFalse(settings._compact_navigation)
        self.assertEqual(settings._menu.width, 150)
        self.assertTrue(layout.set_viewport_width(1100))
        self.assertTrue(device._battery_spacer.visible)
        self.assertEqual(layout.home_content.content.controls, [device, settings.home_controls_card])


if __name__ == "__main__":
    unittest.main()
