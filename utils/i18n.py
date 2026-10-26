"""Small, dependency-free translation catalogs and deferred application messages."""

import ctypes
import json
import locale
import os
import sys
from functools import lru_cache

from .resource_manager import get_resource_path

LANGUAGES = {
    "tr": "Türkçe", "en": "English", "ar": "العربية", "de": "Deutsch",
    "es": "Español", "et": "Eesti", "fi": "Suomi", "fr": "Français",
    "hi": "हिन्दी", "hu": "Magyar", "id": "Bahasa Indonesia", "it": "Italiano",
    "ja": "日本語", "ko": "한국어", "ms": "Bahasa Melayu", "nl": "Nederlands",
    "pl": "Polski", "pt-BR": "Português (Brasil)", "pt-PT": "Português (Portugal)",
    "ru": "Русский", "sv": "Svenska", "th": "ไทย", "uk": "Українська",
    "vi": "Tiếng Việt", "zh-CN": "简体中文", "zh-TW": "繁體中文（台灣）",
    "zh-HK": "繁體中文（香港）",
}
LANGUAGE_CHOICES = ("system", *LANGUAGES)
_language = "en"


def resolve_language(code: str | None) -> str:
    code = (code or "").split(".")[0].split("@")[0].replace("_", "-").lower()
    parts = code.split("-")
    language = {"in": "id"}.get(parts[0], parts[0])
    if language == "zh":
        if "hans" in parts:
            return "zh-CN"
        if "hk" in parts or "mo" in parts:
            return "zh-HK"
        if "hant" in parts or "tw" in parts:
            return "zh-TW"
        return "zh-CN"
    if language == "pt":
        return "pt-BR" if "br" in parts else "pt-PT"
    return language if language in LANGUAGES else "en"


def system_language() -> str:
    if sys.platform == "win32":
        try:
            buffer = ctypes.create_unicode_buffer(85)
            if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
                return resolve_language(buffer.value)
        except (AttributeError, OSError):
            pass
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if os.environ.get(name):
            return resolve_language(os.environ[name])
    try:
        return resolve_language(locale.getlocale()[0])
    except (ValueError, TypeError):
        return "en"


@lru_cache(maxsize=len(LANGUAGES))
def load_catalog(language: str) -> dict[str, str]:
    if language not in LANGUAGES:
        language = "en"
    try:
        with open(get_resource_path(f"assets/locales/{language}.json"), encoding="utf-8") as file:
            data = json.load(file)
        return {key: value for key, value in data.items() if isinstance(value, str)}
    except (OSError, ValueError, AttributeError):
        return {}


def set_language(preference: str) -> str:
    global _language
    _language = system_language() if preference == "system" else resolve_language(preference)
    return _language


def get_language() -> str:
    return _language


def is_rtl() -> bool:
    return _language == "ar"


class Message(str):
    """A string-compatible message that retains its key and unformatted arguments.

    Controllers keep the English string for existing callback consumers. UI code
    renders it in the active language, including nested messages, at display time.
    """

    def __new__(cls, key: str, params: dict, language: str = "en"):
        english = load_catalog("en").get(key, key)
        template = load_catalog(language).get(key, english)
        values = {name: render(value, language) for name, value in params.items()}
        try:
            value = template.format(**values)
        except (KeyError, ValueError, IndexError):
            value = english.format(**values)
        obj = super().__new__(cls, value)
        obj.key, obj.params, obj.language = key, dict(params), language
        return obj

    def __reduce__(self):
        return (Message, (self.key, self.params, self.language))


def message(key: str, **params) -> Message:
    return Message(key, params)


def t(key: str, **params) -> Message:
    return Message(key, params, _language)


def render(value, language: str | None = None):
    if isinstance(value, Message):
        return Message(value.key, value.params, language or _language)
    return value


def error_message(error: Exception) -> str:
    """Keep localized exceptions intact; preserve unknown OS details verbatim."""
    if error.args and isinstance(error.args[0], Message):
        return error.args[0]
    text = str(error)
    for key, value in load_catalog("en").items():
        if value == text:
            return message(key)
    return text or type(error).__name__
