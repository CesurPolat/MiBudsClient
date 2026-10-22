"""Catalog source fidelity and identity integration checks (no hardware)."""

import json
from pathlib import Path
import unittest

from bluetooth.device_catalog import DEVICE_MODEL_NAMES, get_device_models
from bluetooth.rcsp import DeviceIdentity


class DeviceCatalogTests(unittest.TestCase):
    def test_all_app_fields_are_available_through_identity(self):
        source = Path(__file__).resolve().parents[1] / "assets" / "device_catalog.json"
        products = json.loads(source.read_text(encoding="utf-8-sig"))["result"]["tw_product_list"]
        for product in products:
            with self.subTest(model=product["model"]):
                identity = DeviceIdentity(int(product["vid"], 16), int(product["pid"], 16))
                self.assertIn(product, identity.models)
                self.assertIn(product["name"], identity.model_name)

    def test_app_resolves_legacy_name_ambiguity(self):
        self.assertEqual(DEVICE_MODEL_NAMES[(0x2717, 20525)], "Xiaomi Buds 3T Pro")

    def test_variants_do_not_inherit_unconfirmed_functions(self):
        self.assertEqual(get_device_models(0x2717, 20634), ())
        self.assertEqual(DEVICE_MODEL_NAMES[(0x2717, 20634)], "Redmi Buds 6 Play")
        self.assertEqual(DeviceIdentity(0xFFFF, 0xFFFF).models, ())

    def test_nested_metadata_cannot_mutate_catalog(self):
        model = get_device_models(0x2717, 20635)[0]
        model["func_list"].clear()
        model["extra_info"]["sale_model"] = "changed"
        original = get_device_models(0x2717, 20635)[0]
        self.assertTrue(original["func_list"])
        self.assertEqual(original["extra_info"]["sale_model"], "M2420E1")


if __name__ == "__main__":
    unittest.main()
