"""The resource importer is offline, scoped by locale, and preserves desktop text."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET

from tools import import_xiaomi_translations as importer
from utils.i18n import LANGUAGES, load_catalog


class XiaomiTranslationTests(unittest.TestCase):
    def write_xml(self, root, directory, values):
        target = root / directory / "strings.xml"
        target.parent.mkdir(parents=True, exist_ok=True)
        resource = ET.Element("resources")
        for key, value in values.items():
            ET.SubElement(resource, "string", name=key).text = value
        ET.ElementTree(resource).write(target, encoding="utf-8", xml_declaration=True)

    def test_android_escapes_preserve_unicode_and_nested_text(self):
        element = ET.fromstring(r'''<string>Çince \'中文\'\n<b>耳机</b>\t\u4f60</string>''')
        self.assertEqual(importer.android_text(element), "Çince '中文'\n耳机\t你")

    def test_language_layers_do_not_mix_sibling_regions(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            self.write_xml(source, "zh/values-zh", {"base": "base", "shared": "base"})
            self.write_xml(source, "zh/values-zh-rCN", {"shared": "简体", "cn": "cn"})
            self.write_xml(source, "zh/values-zh-rTW", {"shared": "繁體", "tw": "tw"})
            self.write_xml(source, "in/values-in", {"language": "Bahasa Indonesia"})
            tw, paths = importer.collect(source, "zh-TW")
            self.assertEqual(tw, {"base": "base", "shared": "繁體", "tw": "tw"})
            self.assertEqual(paths["shared"], "zh/values-zh-rTW/strings.xml")
            self.assertEqual(importer.collect(source, "id")[0]["language"], "Bahasa Indonesia")

    def test_import_is_dry_run_by_default_and_preserves_custom_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            locales = root / "assets/locales"
            locales.mkdir(parents=True)
            (root / "docs").mkdir()
            source = root / "source"
            original = {"nav.settings": "Settings", "auto.description": "Desktop policy", "action.play": "Play / pause"}
            for language in ("en", "tr"):
                (locales / f"{language}.json").write_text(json.dumps(original), encoding="utf-8")
            self.write_xml(source, "tr/values-tr", {
                "device_settings_translate_setting": "Ayarlar",
                "device_settings_play_or_pause": "%1$s",
                "device_settings_auto_gaming_mode": "Otomatik oyun modu",
            })
            with patch.object(importer, "ROOT", root), patch.object(importer, "LANGUAGES", {"en": "English", "tr": "Türkçe"}):
                changes, _ = importer.import_catalogs(source)
                self.assertEqual(changes, 1)
                self.assertEqual(json.loads((locales / "tr.json").read_text(encoding="utf-8")), original)
                self.assertFalse((root / "docs/localization_sources.json").exists())
                changes, report = importer.import_catalogs(source, write=True)
            result = json.loads((locales / "tr.json").read_text(encoding="utf-8"))
            self.assertEqual(result["nav.settings"], "Ayarlar")
            self.assertEqual(result["auto.description"], "Desktop policy")
            self.assertEqual(result["action.play"], "Play / pause")
            self.assertEqual(json.loads((locales / "en.json").read_text(encoding="utf-8")), original)
            self.assertEqual(len(report["files_sha256"]), 1)

    def test_context_mismatches_are_not_blindly_imported(self):
        keys = importer.resource_keys("zh-CN")
        self.assertEqual(keys["side.left"], "device_settings_left")
        self.assertEqual(keys["battery.right"], "device_settings_right")
        self.assertNotIn("tray.open", keys)
        self.assertNotIn("action.none", importer.resource_keys("pt-BR"))
        self.assertNotIn("action.noise", importer.RESOURCE_KEYS)
        self.assertNotIn("auto.description", importer.RESOURCE_KEYS)

    def test_source_ledger_covers_catalogs_without_external_source_dependency(self):
        root = Path(__file__).resolve().parents[1]
        report = json.loads((root / "docs/localization_sources.json").read_text(encoding="utf-8"))
        self.assertEqual(set(report["locales"]), set(LANGUAGES))
        for language, coverage in report["locales"].items():
            with self.subTest(language=language):
                self.assertEqual(set(coverage["imported"]) | set(coverage["authored"]), set(load_catalog(language)))
                self.assertFalse(set(coverage["imported"]) & set(coverage["authored"]))
                for item in coverage["imported"].values():
                    self.assertIn(item["file"], report["files_sha256"])
