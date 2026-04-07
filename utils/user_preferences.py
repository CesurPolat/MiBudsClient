"""Persisted user preferences for the application."""

import json
import os
from typing import Any, Dict


DEFAULT_LOW_LATENCY_EXCEPTIONS = [
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
    # Linux/X11 WM_CLASS values
    "google-chrome",
    "microsoft-edge",
    "firefox",
    "brave-browser",
    "opera",
    "vivaldi-stable",
    "chromium-browser",
]


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


def get_low_latency_exceptions() -> list[str]:
    """Return process/class names that should not trigger auto low latency."""
    settings = _load_settings()
    values = settings.get("low_latency_exceptions")
    if not isinstance(values, list):
        return list(DEFAULT_LOW_LATENCY_EXCEPTIONS)

    cleaned: list[str] = []
    for item in values:
        if isinstance(item, str) and item.strip():
            cleaned.append(item.strip().lower())

    if not cleaned:
        return list(DEFAULT_LOW_LATENCY_EXCEPTIONS)
    return cleaned


def set_low_latency_exceptions(exceptions: list[str]) -> None:
    """Persist process/class names excluded from auto low latency switching."""
    cleaned = [item.strip().lower() for item in exceptions if isinstance(item, str) and item.strip()]
    settings = _load_settings()
    settings["low_latency_exceptions"] = cleaned
    _save_settings(settings)
