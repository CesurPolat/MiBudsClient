"""Import reviewed, semantically matching Android resources into local catalogs.

Usage: python tools/import_xiaomi_translations.py SOURCE [--write]
Without --write, report differences only. Never reads an APK or contacts a service.
Desktop-specific translations remain in the catalogs and are not overwritten.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.i18n import LANGUAGES

# Only equivalent UI concepts: ANC is not the broader "Noise control" action,
# and Android "Automatic game mode" is not our desktop app-detection policy.
RESOURCE_KEYS = {
    "nav.back": "actionbar_button_up_description",
    "nav.settings": "device_settings_translate_setting",
    "latency.off": "already_close",
    "latency.auto": "exo_track_selection_auto",
    "latency.on": "already_open",
    "battery.left": "device_settings_find_side_left",
    "battery.right": "device_settings_find_side_right",
    "battery.case": "device_settings_box",
    "side.left": "device_settings_find_side_left",
    "side.right": "device_settings_find_side_right",
    "connection.connecting": "device_manager_connecting",
    "connection.connected": "device_connected",
    "connection.retry": "click_to_retry",
    "connection.lost": "device_disconnected",
    "gesture.title": "device_settings_gesture_operation",
    "gesture.single": "device_settings_dongle_click",
    "gesture.double": "device_settings_dongle_double_click",
    "gesture.long": "device_settings_dongle_long_press",
    "action.assistant": "device_settings_awake_voice_assistant",
    "action.play": "device_settings_play_or_pause",
    "action.previous": "device_settings_last_song",
    "action.next": "device_settings_next_song",
    "action.volume_up": "device_settings_volume_up",
    "action.volume_down": "device_settings_volume_down",
    "action.none": "device_settings_click_cancle",
    "action.photo": "device_settings_gesture_quick_photo",
    "action.record": "device_settings_gesture_long_press_record",
    "action.track": "device_settings_gesture_previous_next",
    "auto.remove": "device_settings_remove_device_confirm",
    "update.download": "common_region_unavailable_update_action",
    "tray.open": "device_settings_head_for",
    "tray.quit": "quit",
    "mode.low": "device_settings_spatial_audio_low_latency",
    "mode.standard": "device_settings_scene_standard",
}

# The alarm selector says "Left" in English but "Left only" in Chinese.
# Use the neutral side labels there. "Go to" and "N/A" are also unsuitable
# for opening the app and an unassigned gesture, respectively.
AUTHORED_OVERRIDES = {
    "zh-CN": {"tray.open": "打开"},
    "zh-TW": {"tray.open": "開啟"},
    "zh-HK": {"tray.open": "開啟"},
    "pt-BR": {"action.none": "Não atribuído"},
    "pt-PT": {"action.none": "Não atribuído"},
}


def resource_keys(language):
    result = dict(RESOURCE_KEYS)
    if language.startswith("zh-"):
        for prefix in ("battery", "side"):
            result[f"{prefix}.left"] = "device_settings_left"
            result[f"{prefix}.right"] = "device_settings_right"
    for key in AUTHORED_OVERRIDES.get(language, {}):
        result.pop(key, None)
    return result


def resource_directories(language):
    """Android base + meaningful regional overlay, never sibling-region overlays."""
    if language.startswith("zh-"):
        region = language.split("-")[1]
        return ["zh/values-zh", f"zh/values-zh-r{region}"]
    if language.startswith("pt-"):
        region = language.split("-")[1]
        return ["pt/values-pt", f"pt/values-pt-r{region}"]
    if language == "id":
        return ["in/values-in"]
    if language == "ms":
        return ["ms/values-ms", "ms/values-ms-rMY"]
    if language == "et":
        return ["et/values-et", "et/values-et-rEE"]
    return [f"{language}/values-{language}"]


def android_text(element):
    value = "".join(element.itertext())
    # Decode Android escapes without corrupting non-ASCII UTF-8 characters.
    value = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), value)
    escapes = {"n": "\n", "t": "\t", "r": "\r", "'": "'", '"': '"', "\\": "\\", "@": "@", "?": "?"}
    value = re.sub(r"\\([ntr'\"\\@?])", lambda m: escapes[m[1]], value)
    return value.strip()


def collect(source, language):
    resources, paths = {}, {}
    for directory in resource_directories(language):
        path = source / directory / "strings.xml"
        if not path.exists():
            continue
        for element in ET.parse(path).getroot().findall("string"):
            key = element.get("name")
            resources[key] = android_text(element)
            paths[key] = path.relative_to(source).as_posix()
    return resources, paths


def import_catalogs(source, write=False):
    source = Path(source)
    english = json.loads((ROOT / "assets/locales/en.json").read_text(encoding="utf-8"))
    report = {"source": "Xiaomi Earbuds 1.37.1i extracted XML resources", "locales": {}, "files_sha256": {}}
    changes = 0
    for language in LANGUAGES:
        path = ROOT / f"assets/locales/{language}.json"
        catalog = json.loads(path.read_text(encoding="utf-8"))
        imported = {}
        if language != "en":  # Preserve the English callback text compatibility contract.
            resources, paths = collect(source, language)
            for key, resource in resource_keys(language).items():
                value = resources.get(resource)
                if not value or value.startswith("@") or re.search(r"%\d*\$?[sdf]|[{}]", value):
                    continue
                imported[key] = {"resource": resource, "file": paths[resource]}
                if catalog.get(key) != value:
                    changes += 1
                    catalog[key] = value
        for key, value in AUTHORED_OVERRIDES.get(language, {}).items():
            if catalog.get(key) != value:
                changes += 1
                catalog[key] = value
        report["locales"][language] = {
            "imported": imported,
            "authored": [key for key in english if key not in imported],
        }
        if write:
            path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for item in imported.values():
            relative = item["file"]
            if relative not in report["files_sha256"]:
                report["files_sha256"][relative] = hashlib.sha256((source / relative).read_bytes()).hexdigest()
    if write:
        (ROOT / "docs/localization_sources.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changes, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    changes, report = import_catalogs(args.source, args.write)
    print(f"{len(report['locales'])} locales; {changes} changed translations" + (" (written)" if args.write else " (dry run)"))
