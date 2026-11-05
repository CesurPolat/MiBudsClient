import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from controllers.bluetooth.capabilities import DeviceCapabilities, resolve_capabilities
from controllers.bluetooth.noise import NoiseState, noise_backend_enabled
from controllers.bluetooth.controller import BTController
from ui.components.settings_card import SettingsCard
from utils.i18n import get_language, set_language, t


class NoiseHomeTests(unittest.TestCase):
    def selected_mode(self, panel):
        return next((str(mode) for mode, button in panel.quick_mode_buttons.items()
                     if button.visible and button.style.bgcolor == "#1976D2"), None)

    def make_card(self, name="Redmi Buds 5 Pro", action=None):
        card = SettingsCard(on_noise_action=action)
        card.set_capabilities(resolve_capabilities(name))
        card.update_connection_state("connected")
        return card

    def test_catalog_card_does_not_authorize_commands(self):
        action = Mock()
        card = self.make_card(action=action)
        self.assertIn(card.noise_card, card.connected_controls.controls)
        self.assertLess(card.connected_controls.controls.index(card.noise_card),
                        card.connected_controls.controls.index(card.equalizer_card))
        self.assertTrue(card.noise.quick_mode.disabled)
        self.assertTrue(card.noise.quick_refresh.disabled)
        self.assertEqual(card.noise.quick_status.value, t("noise.unvalidated"))
        card.noise._act("read")
        card.select_section("noise")
        self.assertIsNone(card.noise.begin("read", 1))
        action.assert_not_called()
        controller = BTController()
        controller._connection = SimpleNamespace(connected=True, session_ready=True)
        controller._device_name = "Redmi Buds 5 Pro"
        controller._noise = Mock()
        with self.assertRaises(ValueError):
            controller.request_noise_settings(session=1)
        controller._noise.read.assert_not_called()

    def test_visibility_follows_connection_and_anc_capability(self):
        card = self.make_card()
        card.update_connection_state("disconnected")
        self.assertFalse(card.noise_card.visible)
        for caps in (resolve_capabilities("Redmi Buds 6 Play"), DeviceCapabilities(),
                     DeviceCapabilities(model="transparency-only", functions=frozenset({1004}))):
            card.set_capabilities(caps)
            card.update_connection_state("connected")
            self.assertFalse(card.noise_card.visible)
            self.assertNotIn(card.noise_card, card.connected_controls.controls)
        # A transparency-only device retains its Settings section.
        self.assertTrue(card._available_sections["noise"])
        self.assertEqual([str(v) for v, b in card.noise.quick_mode_buttons.items() if b.visible], ["0", "2"])

    def test_validated_connection_reads_once_and_views_share_confirmed_state(self):
        caps = resolve_capabilities("Redmi Buds 5 Pro")
        with patch("controllers.bluetooth.noise.VALIDATED_NOISE_MODELS", frozenset({caps.model})):
            self.assertTrue(noise_backend_enabled(caps))
            card = SettingsCard()
            panel = card.noise
            action = Mock(side_effect=lambda operation, **kwargs: panel.begin(operation, 7))
            panel._on_action = action
            card.set_capabilities(caps)
            card.update_connection_state("connected")
            action.assert_called_once_with("read")
            self.assertTrue(panel.quick_mode.disabled)
            token = panel._token
            card.select_section("noise")
            card.select_section("general")
            card.update_connection_state("connected")
            action.assert_called_once_with("read")
            panel.complete(token, NoiseState(1, 0))
            self.assertEqual(self.selected_mode(panel), panel.mode.value)
            self.assertEqual(panel.quick_level.value, 1)
            self.assertFalse(panel.quick_mode.disabled)
            self.assertIsNot(panel.quick_mode, panel.mode)
            self.assertIsNot(panel.quick_mode_buttons[0], panel.mode)
            self.assertEqual(panel.quick_level.divisions, 2)
            self.assertFalse(panel.quick_status.visible)

            panel.quick_mode_buttons[2].on_click(None)
            action.assert_called_with("write", mode=2)
            self.assertEqual(self.selected_mode(panel), "1")
            self.assertTrue(panel.quick_mode.disabled)
            panel.complete(panel._token, NoiseState(2, 0))
            self.assertEqual(self.selected_mode(panel), "2")
            panel._select_level(SimpleNamespace(control=SimpleNamespace(value="99")))
            self.assertEqual(action.call_count, 2)
            panel.notification(7, NoiseState(1, 0))
            panel._select_quick_level(SimpleNamespace(control=SimpleNamespace(value=2)))
            action.assert_called_with("write", mode=1, level=2)
            self.assertEqual(panel.quick_level.value, 1)
            panel.complete(panel._token, NoiseState(1, 2))
            panel.notification(6, NoiseState(0))
            self.assertEqual(self.selected_mode(panel), "1")
            panel.notification(7, NoiseState(0))
            self.assertEqual(self.selected_mode(panel), "0")
            self.assertFalse(panel.quick_level.visible)

            panel._act("read")
            old = panel._token
            panel.complete(old, None, "read failed")
            self.assertEqual(panel.quick_status.value, "read failed")
            self.assertFalse(panel.quick_refresh.disabled)
            panel._act("read")
            old = panel._token
            card.update_connection_state("disconnected")
            card.update_connection_state("connected")
            panel.complete(old, NoiseState(2, 0))
            self.assertIsNone(panel._state)
            self.assertTrue(panel.quick_mode.disabled)

    def test_levels_require_catalog_gears_and_language_preserves_state(self):
        original_language = get_language()
        caps = DeviceCapabilities(model="test", functions=frozenset({1002}))
        try:
            with patch("controllers.bluetooth.noise.VALIDATED_NOISE_MODELS", frozenset({"test"})):
                card = SettingsCard()
                card.set_capabilities(caps)
                card.update_connection_state("connected")
                panel = card.noise
                token = panel.begin("read", 1)
                panel.complete(token, NoiseState(1, 99))
                self.assertFalse(panel.quick_level.visible)
                for language in ("tr", "de", "ar", "en"):
                    set_language(language)
                    card.refresh_translations()
                    self.assertEqual(self.selected_mode(panel), "1")
                    self.assertEqual(panel.quick_mode_buttons[1].content.controls[1].value, t("noise.mode_1"))
        finally:
            set_language(original_language)

    def test_slider_maps_positions_to_sparse_catalog_levels_and_rejects_invalid_input(self):
        caps = DeviceCapabilities(model="test", functions=frozenset({1002}),
                                  options={1002: {"tws_gear": [7, 0, 255]}})
        with patch("controllers.bluetooth.noise.VALIDATED_NOISE_MODELS", frozenset({"test"})):
            card = SettingsCard()
            card.set_capabilities(caps)
            card.update_connection_state("connected")
            panel = card.noise
            token = panel.begin("read", 1)
            panel.complete(token, NoiseState(1, 7))
            action = Mock()
            panel._on_action = action
            for invalid in (-1, 3, .5, None, "nan", "inf"):
                panel._select_quick_level(SimpleNamespace(control=SimpleNamespace(value=invalid)))
            action.assert_not_called()
            panel._select_quick_level(SimpleNamespace(control=SimpleNamespace(value=1)))
            action.assert_called_once_with("write", mode=1, level=0)
            self.assertEqual(panel.quick_level.value, 0)
            self.assertEqual(panel.quick_level_label.value, t("noise.level_value", value=7))
            token = panel.begin("write", 1)
            panel.complete(token, NoiseState(1, 255))
            self.assertEqual(panel.quick_level.value, 2)
            panel.notification(1, NoiseState(1, 8))
            self.assertTrue(panel.quick_level.disabled)
            self.assertEqual(panel.quick_level_label.value, t("noise.unknown", code=8))


if __name__ == "__main__":
    unittest.main()
