"""Implemented controls follow the selected model's catalog function list.

Function IDs are UI capabilities, never RFCOMM configuration IDs. Custom EQ
is intentionally deferred; unknown/unimplemented functions remain metadata.
"""
from dataclasses import dataclass, field
import json
import re
from .device_catalog import get_device_models_by_name
from .equalizer import PROFILE_KEYS
from .gestures import GESTURE_FUNCTION_TYPES

FUNCTIONS = {
    1006: "FUNC_ANC_NOISE_FOUR",
    1003: "FUNC_ANC_NOISE_SIX",
    1002: "FUNC_ANC_NOISE_THREE",
    1007: "FUNC_ANC_NOISE_TWO",
    1005: "FUNC_ANC_TRANSPARENT_THREE",
    1004: "FUNC_ANC_TRANSPARENT_TWO",
    2019: "FUNC_AUDIBILITY_ADAPTATION",
    2020: "FUNC_AUDIO_MODE",
    3009: "FUNC_AUTO_GAMING_MODE",
    3008: "FUNC_AUTO_PICK_CALL",
    5005: "FUNC_BEGINNER_GUIDE",
    3010: "FUNC_CUSTOM_SKIN",
    5002: "FUNC_DEVICE_INTRODUCE",
    5003: "FUNC_DEVICE_RECORD",
    5008: "FUNC_DEVICE_TRANSLATE",
    4012: "FUNC_DOUBLE_MFB",
    3004: "FUNC_DUAL_DEVICE_CONNECTION",
    3015: "FUNC_EARBOX_SOUND",
    3013: "FUNC_EAR_CANAL_DETECTION",
    5006: "FUNC_EXERCISE_REPORT",
    5001: "FUNC_FIND_DEVICE",
    5004: "FUNC_FIRMWARE_UPDATE",
    3003: "FUNC_FIT_DETECT",
    4001: "FUNC_GESTURE_DOUBLE_CLICK",
    4003: "FUNC_GESTURE_LONG_PRESS",
    4006: "FUNC_GESTURE_PRESS_ONCE",
    4005: "FUNC_GESTURE_PRESS_TRIPLE",
    4004: "FUNC_GESTURE_PRESS_TWICE",
    4011: "FUNC_GESTURE_SLIDE",
    4002: "FUNC_GESTURE_TRIPLE_CLICK",
    3006: "FUNC_HEARING_HEALTH",
    6001: "FUNC_LABORATORY_NOISE",
    6002: "FUNC_LABORATORY_WEAR_DETECTION",
    4017: "FUNC_LONG_PRESS_ADD_AND_REDUCE",
    4014: "FUNC_LONG_PRESS_MFB",
    4016: "FUNC_LONG_PRESS_MFB_AND_REDUCE",
    4015: "FUNC_LONG_PRESS_REDUCE",
    3011: "FUNC_LOW_LATENCY",
    1009: "FUNC_NOISE_IMMERSE",
    3007: "FUNC_NOTIFICATION",
    3014: "FUNC_NOTIFICATION_TTS",
    2021: "FUNC_NOTIFICATION_VOLUME",
    4018: "FUNC_ONCE_MFB",
    3012: "FUNC_PERSONALIZED_NOISE_REDUCTION",
    2018: "FUNC_PERSONAL_SPATIAL_AUDIO",
    3001: "FUNC_SMART_FREE_PICK",
    1008: "FUNC_SMART_NOISE_REDUCTION",
    2009: "FUNC_SOUND_EFFECT_RENDERING",
    2008: "FUNC_SOUND_SETTINGS_ADAPTIVE_SENSE",
    2017: "FUNC_SOUND_SETTINGS_ADAPTIVE_VOLUME",
    2006: "FUNC_SOUND_SETTINGS_SOUND_MODE",
    2016: "FUNC_SOUND_SETTINGS_SOUND_MODE_OTA",
    2007: "FUNC_SOUND_SETTINGS_SPATIAL_AUDIO_NOTIFY",
    2002: "FUNC_SOUND_SETTING_CLOSE_SPATIAL_AUDIO",
    2004: "FUNC_SOUND_SETTING_SPATIAL_AUDIO_HEAD_TRACKING",
    2003: "FUNC_SOUND_SETTING_SPATIAL_AUDIO_PREFERENCE",
    2005: "FUNC_SOUND_SETTING_SPATIAL_AUDIO_VIRTUAL_SURROUND",
    2001: "FUNC_SOUND_SETTING_VIRTUAL_SURROUND",
    8001: "FUNC_SWIM_LENGTH",
    4013: "FUNC_TRIPLE_MFB",
    7003: "FUNC_USB_CLICK",
    7004: "FUNC_USB_DOUBLE_CLICK",
    7002: "FUNC_USB_EAR_MONITOR",
    7005: "FUNC_USB_LONG_PRESS",
    7001: "FUNC_USB_MODE",
    3005: "FUNC_VOICE_CONTROL",
    3002: "FUNC_WEAR_DETECTION",
    5009: "SUPER_AI",
}

# Register implemented features, not model names. A new catalog model can use
# these controls without requiring a source-code allowlist entry.
COMPONENT_REGISTRY = {"eq": (2006, 2016),
                      "gestures": tuple(GESTURE_FUNCTION_TYPES), "latency": (3011,),
                      "noise": (1002, 1003, 1004, 1005, 1006, 1007)}


def normalize(name):
    return " ".join(name.split()).casefold()


@dataclass(frozen=True)
class DeviceCapabilities:
    model: str = ""
    name: str = ""
    identity: tuple = ()
    functions: frozenset = frozenset()
    options: dict = field(default_factory=dict)
    available: frozenset = frozenset()
    profiles: tuple = ()
    gestures: dict = field(default_factory=dict)
    catalog_effects: tuple = ()

    def supports(self, feature):
        return feature in self.available


def resolve_capabilities(device_name="", identity=None):
    candidates = identity.models if identity is not None else get_device_models_by_name(device_name)
    exact = [item for item in candidates if normalize(item["name"]) == normalize(device_name)]
    candidates = exact if exact else candidates
    if len(candidates) != 1:
        return DeviceCapabilities()
    model = candidates[0]
    options, function_ids = {}, set()
    for function in model.get("func_list", []):
        fid = function.get("func_id")
        if type(fid) is int:
            function_ids.add(fid)
            try:
                data = json.loads(function.get("extra_data"))
            except (ValueError, TypeError):
                # The bundled Xiaomi Buds 4 Pro effects array contains a
                # full-width comma between numeric IDs. Repair only that typo.
                raw = function.get("extra_data")
                if fid != 2016 or not isinstance(raw, str):
                    continue
                try:
                    data = json.loads(re.sub(r"(?<=\d)\uff0c(?=\d)", ",", raw))
                except ValueError:
                    continue
            if isinstance(data, dict):
                options[fid] = data
    functions = frozenset(function_ids)
    effects = options.get(2016, {}).get("sound_effect", {})
    effects = effects.get("effects", []) if isinstance(effects, dict) else effects
    effects = tuple(v for v in effects if type(v) is int) if isinstance(effects, list) else ()
    catalog_effects = effects
    if not catalog_effects:
        legacy = options.get(2006, {}).get("sound_effect", [])
        if isinstance(legacy, list):
            catalog_effects = tuple(v for v in legacy if type(v) is int)
    profiles = tuple(dict.fromkeys(v for v in catalog_effects if v in PROFILE_KEYS and v != 10))
    gestures = {}
    for fid, gesture in GESTURE_FUNCTION_TYPES.items():
        actions = options.get(fid, {}).get("click_action")
        if isinstance(actions, list):
            allowed = tuple(dict.fromkeys(v for v in actions if type(v) is int and v in range(14)))
            if allowed:
                gestures[gesture] = allowed
    available = {feature for feature, ids in COMPONENT_REGISTRY.items()
                 if any(fid in functions for fid in ids)}
    # Battery is basic device telemetry and has no func_list feature ID.
    available.add("battery")
    # Never grant custom_eq, even when effects contains 10: deferred by request.
    return DeviceCapabilities(model["model"], model["name"],
                              (model.get("vid"), model.get("pid")), functions,
                              options, frozenset(available), profiles, gestures,
                              tuple(dict.fromkeys(catalog_effects)))
