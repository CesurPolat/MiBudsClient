"""Catalog integrity, persisted locale selection, and deferred message rendering."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from string import Formatter
from unittest.mock import patch

from utils.i18n import (
    Message, error_message, get_language, load_catalog, message, render,
    resolve_language, set_language, system_language, t,
)
from utils.user_preferences import get_language_preference, set_language_preference


class TranslationTests(unittest.TestCase):
    def tearDown(self):
        set_language("en")

    def test_catalogs_have_identical_keys_and_named_parameters(self):
        english = load_catalog("en")
        self.assertTrue(english)
        formatter = Formatter()
        for language in ("tr", "zh-CN"):
            catalog = load_catalog(language)
            self.assertEqual(catalog.keys(), english.keys())
            for key, value in english.items():
                with self.subTest(language=language, key=key):
                    parameters = lambda text: {name for _, name, _, _ in formatter.parse(text) if name}
                    self.assertEqual(parameters(value), parameters(catalog[key]))
                    self.assertTrue(catalog[key].strip())
                    self.assertNotIn("?", catalog[key])

    def test_supported_locale_variants_and_unsupported_fallback(self):
        for code, expected in (
            ("tr_TR.UTF-8", "tr"), ("tr-TR", "tr"), ("en_GB", "en"),
            ("zh_CN.UTF-8", "zh-CN"), ("zh-Hans-CN", "zh-CN"),
            ("zh-SG", "zh-CN"), ("zh", "zh-CN"),
            ("zh-TW", "en"), ("zh-Hant", "en"), ("de_DE", "en"),
            (None, "en"), ("C", "en"),
        ):
            with self.subTest(code=code):
                self.assertEqual(resolve_language(code), expected)

    def test_linux_locale_precedence(self):
        with patch("utils.i18n.sys.platform", "linux"), patch.dict(
            os.environ, {"LC_ALL": "tr_TR.UTF-8", "LC_MESSAGES": "zh_CN", "LANG": "en_US"}, clear=True
        ):
            self.assertEqual(system_language(), "tr")
            del os.environ["LC_ALL"]
            self.assertEqual(system_language(), "zh-CN")

    def test_windows_user_locale(self):
        def get_locale(buffer, length):
            buffer.value = "zh-CN"
            return len(buffer.value) + 1
        with patch("utils.i18n.sys.platform", "win32"), patch("utils.i18n.ctypes.windll", create=True) as api:
            api.kernel32.GetUserDefaultLocaleName.side_effect = get_locale
            self.assertEqual(system_language(), "zh-CN")

    def test_system_preference_is_resolved_each_time(self):
        with patch("utils.i18n.system_language", return_value="tr"):
            self.assertEqual(set_language("system"), "tr")
        with patch("utils.i18n.system_language", return_value="zh-CN"):
            self.assertEqual(set_language("system"), "zh-CN")

    def test_fallback_to_english_for_missing_or_invalid_translation(self):
        def catalog(language):
            return {"test": "Value: {value}"} if language == "en" else {"test": "{wrong}"}
        set_language("tr")
        with patch("utils.i18n.load_catalog", side_effect=catalog):
            self.assertEqual(t("test", value=42), "Value: 42")
            self.assertEqual(t("missing"), "missing")

    def test_missing_catalog_falls_back_to_english(self):
        load_catalog.cache_clear()
        original = __import__("builtins").open
        def open_catalog(path, *args, **kwargs):
            if str(path).endswith("tr.json"):
                raise FileNotFoundError(path)
            return original(path, *args, **kwargs)
        try:
            with patch("builtins.open", side_effect=open_catalog):
                set_language("tr")
                self.assertEqual(t("nav.settings"), "Settings")
        finally:
            load_catalog.cache_clear()

    def test_deferred_message_keeps_english_callback_and_nested_parameters(self):
        value = message("connection.technical", reason=message("connection.permission"), details="OS error 123")
        set_language("zh-CN")
        self.assertIn("Bluetooth access was denied", value)
        translated = render(value)
        self.assertIsInstance(translated, Message)
        self.assertIn("蓝牙访问被拒绝", translated)
        self.assertIn("OS error 123", translated)
        self.assertEqual(translated.key, "connection.technical")
        set_language("tr")
        self.assertIn("Bluetooth erişimi reddedildi", render(copy.deepcopy(translated)))

    def test_localized_exceptions_and_raw_technical_details(self):
        value = message("gesture.timeout")
        self.assertIs(error_message(TimeoutError(value)), value)
        self.assertEqual(error_message(OSError("OS error 123")), "OS error 123")
        set_language("tr")
        self.assertEqual(render(error_message(ValueError("Invalid gesture config record length"))),
                         "Geçersiz hareket ayarı kayıt uzunluğu")

    def test_preferences_preserve_existing_settings_and_reject_invalid_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            with patch("utils.user_preferences._settings_file_path", return_value=str(path)):
                self.assertEqual(get_language_preference(), "system")
                path.write_text(json.dumps({"low_latency_mode": "auto", "skipped_update_version": "v1.2.3"}), encoding="utf-8")
                for language in ("tr", "en", "zh-CN", "system"):
                    set_language_preference(language)
                    self.assertEqual(get_language_preference(), language)
                set_language_preference("invalid")
                self.assertEqual(get_language_preference(), "system")
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(data["low_latency_mode"], "auto")
                self.assertEqual(data["skipped_update_version"], "v1.2.3")
                for invalid in ("invalid", None, [], {}):
                    data["language"] = invalid
                    path.write_text(json.dumps(data), encoding="utf-8")
                    self.assertEqual(get_language_preference(), "system")


if __name__ == "__main__":
    unittest.main()
