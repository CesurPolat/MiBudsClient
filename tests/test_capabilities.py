"""Model metadata must never grant an unimplemented device protocol."""
import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from controllers.bluetooth.capabilities import (
    DeviceCapabilities, FUNCTIONS, resolve_capabilities,
)
from controllers.bluetooth.device_catalog import get_device_models_by_name
from controllers.bluetooth.controller import BTController
from controllers.bluetooth.equalizer import EqResult, EqState
from controllers.bluetooth.eq_transport import EqTransport
from ui.components.settings_card import SettingsCard
from ui.system_tray import SystemTray
from controllers.latency.controller import LatencyController
from controllers.device.catalog_sync import CatalogSync


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.play = get_device_models_by_name("Redmi Buds 6 Play")[0]

    def resolve(self, models, name="Redmi Buds 6 Play"):
        return resolve_capabilities(name, SimpleNamespace(models=models))

    def with_effects(self, effects):
        model = deepcopy(self.play)
        for func in model["func_list"]:
            if func["func_id"] == 2016:
                func["extra_data"] = json.dumps({"sound_effect": {"effects": effects}})
        return model

    def test_registry_and_all_bundled_models(self):
        self.assertNotIn(1001, FUNCTIONS)
        self.assertEqual(FUNCTIONS[4018], "FUNC_ONCE_MFB")
        from controllers.bluetooth.device_catalog import _APP_CATALOG
        for model in _APP_CATALOG["result"]["tw_product_list"]:
            caps = self.resolve([model], model["name"])
            self.assertEqual(caps.model, model["model"])
            self.assertEqual(caps.functions, frozenset(f["func_id"] for f in model["func_list"]))
            if model["model"] != self.play["model"]:
                self.assertFalse(caps.available)

    def test_identity_candidates_are_not_merged(self):
        other = get_device_models_by_name("REDMI Headphones Neo")[0]
        self.assertEqual(self.resolve([other, self.play]).model, self.play["model"])
        self.assertFalse(self.resolve([other, self.play], "renamed").available)
        self.assertEqual(self.resolve([other], "renamed").model, other["model"])
        self.assertFalse(self.resolve([]).available)

    def test_metadata_limits_and_custom_eq(self):
        caps = self.resolve([self.with_effects([0, 10, 999, True, 0])])
        self.assertEqual(caps.profiles, (0,))
        self.assertTrue(caps.supports("custom_eq"))
        self.assertFalse(self.resolve([self.play]).supports("custom_eq"))
        model = self.with_effects([])
        for func in model["func_list"]:
            if func["func_id"] in (2016, 4001, 4002, 4003, 4006, 3011):
                func["extra_data"] = "broken JSON"
        caps = self.resolve([model])
        self.assertFalse(caps.supports("eq"))
        self.assertFalse(caps.supports("gestures"))
        self.assertFalse(caps.supports("latency"))

    def test_unknown_model_cannot_copy_play_backend(self):
        model = deepcopy(self.play)
        model["model"] = "new.model"
        self.assertFalse(self.resolve([model]).available)

    def test_ui_filters_sections_and_rejects_old_completion(self):
        card = SettingsCard()
        card.set_capabilities(self.resolve([self.play]))
        card.update_connection_state("connected")
        self.assertTrue(card.gestures.visible)
        self.assertTrue(card.equalizer.visible)
        self.assertFalse(card.equalizer.custom_supported)
        token = card.equalizer.begin("read")
        card.set_capabilities(resolve_capabilities("REDMI Headphones Neo"))
        card.equalizer.complete(token, EqResult(True, EqState(0), "old"), (0,), "read")
        self.assertIsNone(card.equalizer._state)
        self.assertFalse(card.gestures.visible)
        self.assertFalse(card.equalizer.visible)
        self.assertEqual(card.connected_controls.controls, [])
        self.assertTrue(card.noise.visible)  # Noise functions are available independently.
        self.assertEqual(len(card.content.controls), 7)  # four sections, three dividers
        card.update_connection_state("failed")
        self.assertFalse(card.connected_controls.visible)

    def test_controller_rejects_unsupported_commands(self):
        controller = BTController()
        controller._connection.connected = True
        controller._device_name = "REDMI Headphones Neo"
        controller._connection.send = Mock()
        self.assertFalse(controller.send_command()[0])
        self.assertFalse(controller.request_battery()[0])
        self.assertFalse(controller.request_eq_settings().success)
        self.assertFalse(controller.request_gesture_settings().success)
        controller.on_connect_setup()
        controller._connection.send.assert_not_called()

    def test_play_cannot_write_custom_eq_without_effect_10(self):
        controller = BTController()
        controller._connection.connected = True
        controller._device_name = "Redmi Buds 6 Play"
        controller._equalizer.apply = Mock()
        self.assertFalse(controller.apply_eq("save").success)
        controller._equalizer.apply.assert_not_called()

    def test_catalog_capabilities_refresh_without_image_change(self):
        client, publish = Mock(), Mock()
        client.load_last_device_image.return_value = ("", "")
        client.cache_image.return_value = ""
        sync = CatalogSync(publish=publish, get_identity=lambda: None,
                           get_device_name=lambda: "Redmi Buds 6 Play",
                           app_version="v1.0.0", client=client)
        before = self.resolve([self.play])
        after = self.resolve([self.with_effects([0, 10])])
        with patch("controllers.device.catalog_sync.resolve_capabilities", side_effect=[before, after]):
            sync._publish_device()
            sync._publish_device()
        types = [call.args[0]["type"] for call in publish.call_args_list]
        self.assertEqual(types.count("capabilities_changed"), 2)
        self.assertEqual(types.count("catalog_device"), 1)

    def test_no_custom_config_query_for_presets_only(self):
        transport = EqTransport(SimpleNamespace(generation=0, transaction=Mock()))
        transport.channel.transaction.return_value.__enter__ = Mock()
        transport.channel.transaction.return_value.__exit__ = Mock(return_value=False)
        transport._exchange = Mock(return_value=bytes.fromhex("03000700"))
        self.assertTrue(transport.read(custom=False).success)
        self.assertEqual(transport._exchange.call_count, 1)
        self.assertEqual(transport._exchange.call_args.args[2], 7)

    def test_tray_and_automatic_mode_cannot_send(self):
        callback = Mock()
        tray = SystemTray(Mock(), Mock(), callback, latency_available=lambda: False)
        tray._on_mode_select("on")
        callback.assert_not_called()
        device = SimpleNamespace(capabilities=DeviceCapabilities(), send_command=Mock())
        with patch("controllers.latency.controller.get_low_latency_mode", return_value="off"):
            latency = LatencyController(Mock(), lambda: device, lambda: None, Mock(), Mock())
        self.assertFalse(latency.set_effective_latency_state(True))
        latency.apply_monitor_latency_policy(True, "game.exe")
        latency.state["effective_low_latency"] = True
        latency.set_device_capabilities(DeviceCapabilities())
        self.assertFalse(latency.state["effective_low_latency"])
        device.send_command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
