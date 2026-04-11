"""Persisted user preferences for the application."""

import json
import os
import sys
from typing import Any, Dict


LOW_LATENCY_MODES = {"off", "auto", "on"}
DEFAULT_LOW_LATENCY_MODE = "off"
DEFAULT_LOW_LATENCY_HOLD_UNTIL_APP_CLOSE = True


DEFAULT_LOW_LATENCY_EXCEPTIONS_WINDOWS = [
    "explorer.exe",
    "vlc.exe",
    "mpc-hc64.exe",
    "mpv.exe",
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "opera_gx.exe",
    "vivaldi.exe",
    "chromium.exe",
]

DEFAULT_LOW_LATENCY_EXCEPTIONS_LINUX = [
    "google-chrome",
    "microsoft-edge",
    "firefox",
    "brave-browser",
    "opera",
    "vivaldi-stable",
    "chromium-browser",
]

DEFAULT_LOW_LATENCY_INCLUDES_WINDOWS: list[str] = []
DEFAULT_LOW_LATENCY_INCLUDES_LINUX: list[str] = []

def _normalize_exceptions(values: list[str]) -> list[str]:
    cleaned = [item.strip().lower() for item in values if isinstance(item, str) and item.strip()]
    return list(dict.fromkeys(cleaned))


def _platform_key(platform: str | None = None) -> str:
    candidate = (platform or "").strip().lower()
    if candidate in {"windows", "linux"}:
        return candidate

    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def _default_exceptions(platform: str) -> list[str]:
    if platform == "windows":
        return list(DEFAULT_LOW_LATENCY_EXCEPTIONS_WINDOWS)
    return list(DEFAULT_LOW_LATENCY_EXCEPTIONS_LINUX)


def _default_includes(platform: str) -> list[str]:
    if platform == "windows":
        return list(DEFAULT_LOW_LATENCY_INCLUDES_WINDOWS)
    return list(DEFAULT_LOW_LATENCY_INCLUDES_LINUX)


def _migrate_legacy_exceptions(settings: Dict[str, Any]) -> bool:
    changed = False

    has_windows = isinstance(settings.get("low_latency_exceptions_windows"), list)
    has_linux = isinstance(settings.get("low_latency_exceptions_linux"), list)
    legacy_values = settings.get("low_latency_exceptions")

    if has_windows and has_linux:
        return False

    migrated_windows: list[str] = []
    migrated_linux: list[str] = []
    if isinstance(legacy_values, list):
        for item in legacy_values:
            if not isinstance(item, str):
                continue
            normalized = item.strip().lower()
            if not normalized:
                continue
            if normalized.endswith(".exe"):
                migrated_windows.append(normalized)
            else:
                migrated_linux.append(normalized)

    if not has_windows:
        settings["low_latency_exceptions_windows"] = (
            _normalize_exceptions(migrated_windows)
            if migrated_windows
            else list(DEFAULT_LOW_LATENCY_EXCEPTIONS_WINDOWS)
        )
        changed = True

    if not has_linux:
        settings["low_latency_exceptions_linux"] = (
            _normalize_exceptions(migrated_linux)
            if migrated_linux
            else list(DEFAULT_LOW_LATENCY_EXCEPTIONS_LINUX)
        )
        changed = True

    return changed


def _settings_file_path() -> str:
    """Return the path to the local settings JSON file."""
    app_data = os.getenv("APPDATA") or os.path.expanduser("~")
    settings_dir = os.path.join(app_data, "MiBudsClient")
    os.makedirs(settings_dir, exist_ok=True)
    return os.path.join(settings_dir, "settings.json")


def _load_settings() -> Dict[str, Any]:
    """Load settings from disk, returning empty defaults on failure."""
    path = _settings_file_path()
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                if _migrate_legacy_exceptions(data):
                    _save_settings(data)
                return data
    except Exception as e:
        print(f"Failed to load settings: {e}")

    return {}


def _save_settings(settings: Dict[str, Any]) -> None:
    """Save settings to disk."""
    path = _settings_file_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"Failed to save settings: {e}")


def should_show_update_notification(latest_version: str) -> bool:
    """Return True if update notification should be shown for this version."""
    settings = _load_settings()
    skipped_version = settings.get("skipped_update_version")
    return skipped_version != latest_version


def suppress_update_notification(latest_version: str) -> None:
    """Store selected version so update notification will not show again for it."""
    settings = _load_settings()
    settings["skipped_update_version"] = latest_version
    _save_settings(settings)


def get_low_latency_exceptions(platform: str | None = None) -> list[str]:
    """Return process names excluded from auto low latency for a platform."""
    target_platform = _platform_key(platform)
    settings = _load_settings()
    key = f"low_latency_exceptions_{target_platform}"
    values = settings.get(key)
    if not isinstance(values, list):
        return _default_exceptions(target_platform)

    cleaned = _normalize_exceptions(values)
    if not cleaned:
        return _default_exceptions(target_platform)
    return cleaned


def get_all_low_latency_exceptions() -> dict[str, list[str]]:
    """Return platform-separated exception lists for Windows and Linux."""
    return {
        "windows": get_low_latency_exceptions("windows"),
        "linux": get_low_latency_exceptions("linux"),
    }


def get_low_latency_includes(platform: str | None = None) -> list[str]:
    """Return process names included for auto low latency for a platform."""
    target_platform = _platform_key(platform)
    settings = _load_settings()
    key = f"low_latency_includes_{target_platform}"
    values = settings.get(key)
    if not isinstance(values, list):
        return _default_includes(target_platform)

    cleaned = _normalize_exceptions(values)
    if not cleaned:
        return _default_includes(target_platform)
    return cleaned


def get_all_low_latency_includes() -> dict[str, list[str]]:
    """Return platform-separated include lists for Windows and Linux."""
    return {
        "windows": get_low_latency_includes("windows"),
        "linux": get_low_latency_includes("linux"),
    }


def set_low_latency_exceptions(exceptions: list[str], platform: str | None = None) -> None:
    """Persist process names excluded from auto low latency for a platform."""
    target_platform = _platform_key(platform)
    key = f"low_latency_exceptions_{target_platform}"
    cleaned = _normalize_exceptions(exceptions)
    settings = _load_settings()
    settings[key] = cleaned
    _save_settings(settings)


def set_low_latency_includes(includes: list[str], platform: str | None = None) -> None:
    """Persist process names included for auto low latency for a platform."""
    target_platform = _platform_key(platform)
    key = f"low_latency_includes_{target_platform}"
    cleaned = _normalize_exceptions(includes)
    settings = _load_settings()
    settings[key] = cleaned
    _save_settings(settings)


def get_low_latency_mode() -> str:
    """Return persisted low latency selection mode: off, auto, or on."""
    settings = _load_settings()
    mode = settings.get("low_latency_mode")
    if isinstance(mode, str):
        normalized = mode.strip().lower()
        if normalized == "include":
            return "auto"
        if normalized in LOW_LATENCY_MODES:
            return normalized
    return DEFAULT_LOW_LATENCY_MODE


def set_low_latency_mode(mode: str) -> None:
    """Persist selected low latency mode if valid."""
    normalized = (mode or "").strip().lower()
    if normalized not in LOW_LATENCY_MODES:
        return

    settings = _load_settings()
    settings["low_latency_mode"] = normalized
    _save_settings(settings)


def get_low_latency_hold_until_app_close() -> bool:
    """Return whether low latency should stay enabled until the app closes."""
    settings = _load_settings()
    value = settings.get("low_latency_hold_until_app_close")
    if isinstance(value, bool):
        return value
    return DEFAULT_LOW_LATENCY_HOLD_UNTIL_APP_CLOSE


def set_low_latency_hold_until_app_close(enabled: bool) -> None:
    """Persist the hold-until-app-close preference."""
    settings = _load_settings()
    settings["low_latency_hold_until_app_close"] = bool(enabled)
    _save_settings(settings)
