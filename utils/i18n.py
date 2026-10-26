"""Small, dependency-free translation catalogs and deferred application messages."""

import ctypes
import json
import locale
import os
import sys
from functools import lru_cache

from .resource_manager import get_resource_path

LANGUAGES = {"tr": "Türkçe", "en": "English", "zh-CN": "简体中文"}
LANGUAGE_CHOICES = ("system", *LANGUAGES)
_language = "en"


def resolve_language(code: str | None) -> str:
    code = (code or "").split(".")[0].split("@")[0].replace("_", "-").lower()
    if code == "tr" or code.startswith("tr-"):
        return "tr"
    if code == "en" or code.startswith("en-"):
        return "en"
    if code in {"zh", "zh-cn", "zh-sg", "zh-hans"} or code.startswith("zh-hans-"):
        return "zh-CN"
    return "en"


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


@lru_cache(maxsize=3)
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
