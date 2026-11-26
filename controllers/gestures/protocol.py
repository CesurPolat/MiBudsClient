"""Catalog-driven gesture records with separate earbud and MFB codecs."""

from dataclasses import dataclass, field

GESTURE_NAMES = {4: "Single tap", 1: "Double tap", 2: "Triple tap", 3: "Long press", 5: "Swipe",
                 4004: "Double squeeze", 4005: "Triple squeeze", 4012: "Double press",
                 4013: "Triple press", 4014: "Long press", 4018: "Single press"}
ACTION_NAMES = {
    0: "Voice assistant", 1: "Play / pause", 2: "Previous track",
    3: "Next track", 4: "Volume up", 5: "Volume down",
    6: "Noise control", 7: "Game mode", 8: "Unassigned", 9: "Take photo",
    10: "Record", 11: "Volume control", 12: "Speech translation",
    13: "Track control",
}
# Catalog function IDs map to physical gestures, then to their wire codec.
# APK GestureControlViewModel.getTwiceType/getTripleType uses the same click
# codec for squeeze variants. Keep physical labels separate from wire types.
GESTURE_FUNCTION_TYPES = {4006: 4, 4001: 1, 4002: 2, 4003: 3, 4011: 5,
                         4004: 4004, 4005: 4005, 4012: 4012, 4013: 4013, 4014: 4014, 4018: 4018}
MFB_OPERATIONS = {4012: 2, 4013: 3, 4014: 4, 4018: 1}
# BoneConductionGestureValue uses different action numbers. 16 has no
# implementation in the inspected source; preserve it on read, don't offer it.
MFB_ACTION_KEYS = {0: "none", 1: "play", 2: "volume_up", 3: "volume_down",
                   4: "previous", 5: "next", 13: "assistant", 15: "noise"}


def actions_for_gesture(gesture):
    return MFB_ACTION_KEYS if gesture in MFB_OPERATIONS else ACTION_NAMES


def gesture_config(gesture):
    return 80 if gesture in MFB_OPERATIONS else 2


@dataclass
class GestureResult:
    success: bool
    assignments: dict[int, tuple[int, int]] = field(default_factory=dict)
    message: str = ""


def gesture_capabilities(device_name: str, identity=None) -> dict[int, tuple[int, ...]]:
    from ..catalog.capabilities import resolve_capabilities
    caps = resolve_capabilities(device_name, identity)
    return caps.gestures if caps.supports("gestures") else {}


def _check_counter(counter: int) -> None:
    if type(counter) is not int or not 0 <= counter <= 255:
        raise ValueError("RCSP counter must fit in one byte")


def build_gesture_request(counter: int, config=2) -> bytes:
    _check_counter(counter)
    return bytes.fromhex(f"fe dc ba c4 f3 00 03 {counter:02x} 00 {config:02x} ef")


def build_gesture_assignment(counter: int, gesture_type: int, side: str, action: int) -> bytes:
    _check_counter(counter)
    if gesture_type not in GESTURE_NAMES or side not in ("left", "right", "common"):
        raise ValueError("Unknown gesture or earbud side")
    if type(action) is not int or action not in actions_for_gesture(gesture_type):
        raise ValueError("Unknown gesture action")
    if gesture_type in MFB_OPERATIONS:
        if side != "common":
            raise ValueError("MFB is a common button, not an earbud side")
        # DeviceConfigClickSetBoneConduction: scene/key/operation/time/function.
        return bytes.fromhex(f"fe dc ba c4 f2 00 09 {counter:02x} 07 00 50 00 01 {MFB_OPERATIONS[gesture_type]:02x} 00 {action:02x} ef")
    if side == "common":
        raise ValueError("Earbud gesture needs a side")
    gesture_type = {4004: 1, 4005: 2}.get(gesture_type, gesture_type)
    left, right = (action, 255) if side == "left" else (255, action)
    return bytes.fromhex(
        f"fe dc ba c4 f2 00 07 {counter:02x} 05 00 02 "
        f"{gesture_type:02x} {left:02x} {right:02x} ef")


def parse_gesture_records(data: bytes, *, physical=False) -> dict[int, tuple[int, int]]:
    """Validate the complete record list before returning any assignments."""
    assignments = {}
    found = False
    from ..bluetooth.packets.config_transport import parse_config_records
    for config_id, value in parse_config_records(data).items():
        if config_id == 2:
            found = True
            if len(value) % 3:
                raise ValueError("Incomplete gesture assignment group")
            for offset in range(0, len(value), 3):
                gesture, left, right = value[offset:offset + 3]
                if gesture in assignments:
                    raise ValueError("Duplicate gesture assignment")
                assignments[gesture] = (left, right)
                if physical and gesture in (1, 2):
                    assignments[{1: 4004, 2: 4005}[gesture]] = (left, right)
        elif config_id == 80:
            found = True
            if len(value) % 5:
                raise ValueError("Incomplete MFB assignment group")
            for offset in range(0, len(value), 5):
                scene, key, operation, duration, action = value[offset:offset + 5]
                # The editor handles the normal scene and MFB key only.
                if scene != 0 or key != 1 or duration != 0:
                    continue
                gesture = next((g for g, op in MFB_OPERATIONS.items() if op == operation), None)
                if gesture is not None:
                    if gesture in assignments:
                        raise ValueError("Duplicate MFB assignment")
                    assignments[gesture] = (action, action)
    if not found:
        raise ValueError("Device response contains no gesture settings")
    return assignments
