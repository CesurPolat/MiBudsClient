"""Redmi gesture config records and packets (hardware validation required)."""

from dataclasses import dataclass, field

GESTURE_NAMES = {4: "Single tap", 1: "Double tap", 2: "Triple tap", 3: "Long press"}
ACTION_NAMES = {
    0: "Voice assistant", 1: "Play / pause", 2: "Previous track",
    3: "Next track", 4: "Volume up", 5: "Volume down",
    6: "Noise control", 7: "Game mode", 8: "Unassigned", 9: "Take photo",
    10: "Record", 11: "Volume control", 12: "Speech translation",
    13: "Track control",
}
# Only confirmed touch gesture function IDs. Do not infer press/swipe variants.
_FUNCTION_TYPES = {4006: 4, 4001: 1, 4002: 2, 4003: 3}
_MODEL = "redmi buds 6 play"


@dataclass
class GestureResult:
    success: bool
    assignments: dict[int, tuple[int, int]] = field(default_factory=dict)
    message: str = ""


def gesture_capabilities(device_name: str, identity=None) -> dict[int, tuple[int, ...]]:
    """Use the exact model record, never a related product's functions."""
    # UI also imports the labels above during package initialization.
    from .device_catalog import get_device_models_by_name
    from utils.mibuds_api import parse_extra_data

    if identity is not None:
        models = identity.models
    else:
        models = get_device_models_by_name(device_name)
    models = [model for model in models if model["name"].strip().casefold() == _MODEL]
    if len(models) != 1:
        return {}
    capabilities = {}
    for function in models[0].get("func_list", []):
        gesture = _FUNCTION_TYPES.get(function.get("func_id"))
        actions = parse_extra_data(function.get("extra_data")).get("click_action")
        if gesture is not None and isinstance(actions, list):
            # Noise control is outside this model's gesture editor scope.
            allowed = tuple(dict.fromkeys(action for action in actions
                            if type(action) is int and action in ACTION_NAMES and action != 6))
            if allowed:
                capabilities[gesture] = allowed
    return capabilities


def _check_counter(counter: int) -> None:
    if type(counter) is not int or not 0 <= counter <= 255:
        raise ValueError("RCSP counter must fit in one byte")


def build_gesture_request(counter: int) -> bytes:
    _check_counter(counter)
    return bytes.fromhex(f"fe dc ba c4 f3 00 03 {counter:02x} 00 02 ef")


def build_gesture_assignment(counter: int, gesture_type: int, side: str, action: int) -> bytes:
    _check_counter(counter)
    if gesture_type not in GESTURE_NAMES or side not in ("left", "right"):
        raise ValueError("Unknown gesture or earbud side")
    if type(action) is not int or action not in ACTION_NAMES:
        raise ValueError("Unknown gesture action")
    left, right = (action, 255) if side == "left" else (255, action)
    return bytes.fromhex(
        f"fe dc ba c4 f2 00 07 {counter:02x} 05 00 02 "
        f"{gesture_type:02x} {left:02x} {right:02x} ef")


def parse_gesture_records(data: bytes) -> dict[int, tuple[int, int]]:
    """Validate the complete record list before returning any assignments."""
    assignments = {}
    found = False
    position = 0
    while position < len(data):
        length = data[position]
        end = position + 1 + length
        if length < 2 or end > len(data):
            raise ValueError("Invalid gesture config record length")
        config_id = int.from_bytes(data[position + 1:position + 3], "big")
        value = data[position + 3:end]
        if config_id == 2:
            found = True
            if len(value) % 3:
                raise ValueError("Incomplete gesture assignment group")
            for offset in range(0, len(value), 3):
                gesture, left, right = value[offset:offset + 3]
                if gesture in assignments:
                    raise ValueError("Duplicate gesture assignment")
                assignments[gesture] = (left, right)
        position = end
    if not found:
        raise ValueError("Device response contains no gesture settings")
    return assignments
