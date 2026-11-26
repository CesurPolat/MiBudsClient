"""Resolve firmware-dependent options without confusing Android/app versions."""
import re
from copy import deepcopy


def version_parts(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d+){3}", value):
        return None
    return tuple(int(part) for part in value.split("."))


def firmware_at_least(current, required):
    current, required = version_parts(current), version_parts(required)
    return current is not None and required is not None and current >= required


def resolve_options(raw, firmware):
    """Last matching OTA entry wins, preserving catalog order (APK policy).

    Nonempty app_version refers to Xiaomi's host app, not MiBudsClient. Without
    that version context leave that alternative unresolved and use base data.
    """
    options = deepcopy(raw)
    unresolved = []
    for fid, data in options.items():
        for key, target, field in (("ota_tws_gear", "tws_gear", "gears"),
                                   ("ota_sound_effect", "sound_effect", "effects")):
            alternatives = data.get(key, [])
            if not isinstance(alternatives, list):
                continue
            for alternative in alternatives:
                if not isinstance(alternative, dict):
                    continue
                if alternative.get("app_version") or version_parts(firmware) is None:
                    unresolved.append((fid, key))
                    continue
                if firmware_at_least(firmware, alternative.get("fw_version")):
                    value = alternative.get(field)
                    if isinstance(value, list):
                        data[target] = value if target == "tws_gear" else {"effects": value}
    return options, tuple(dict.fromkeys(unresolved))
