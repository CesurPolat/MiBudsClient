"""ANC codec and function-list capabilities; not hardware certification."""
from dataclasses import dataclass

from .config_transport import parse_config_records
from .equalizer import _frame


ANC_FUNCTIONS = (1002, 1003, 1006, 1007)
TRANSPARENCY_FUNCTIONS = (1004, 1005)
OLD_ADAPTIVE_MODELS = frozenset(("l76", "l77", "k73", "k73a", "l77s"))
# L71's APK UI explicitly suppresses the generic level names. This is an
# interpretation exception, not a permission gate for this or other models.
SPECIAL_ANC_MODEL = "miwear.headphone.l71g"
ANC_LEVEL_LABELS = {
    0: "noise.anc_balanced", 1: "noise.anc_light", 2: "noise.anc_deep",
    3: "noise.anc_adaptive", 4: "noise.anc_wind", 5: "noise.anc_deep_plus",
}
TRANSPARENCY_LEVEL_LABELS = {
    0: "noise.trans_standard", 1: "noise.trans_voice",
    2: "noise.trans_ambient", 3: "noise.trans_voice_plus",
}


def noise_backend_enabled(caps):
    """ANC/transparency access follows func_list, without a model allowlist."""
    return bool(noise_capabilities(caps).modes)


@dataclass(frozen=True)
class NoiseCapabilities:
    modes: tuple = ()
    anc_levels: tuple = ()
    transparency_levels: tuple = ()
    adaptive: str | None = None
    wear_type: int | None = None
    anc_schema: str = "unknown"
    transparency_schema: str = "unknown"

    def levels(self, mode):
        return self.anc_levels if mode == 1 else self.transparency_levels if mode == 2 else ()

    def special_levels(self, mode):
        if mode == 1 and self.anc_schema == "discrete_legacy":
            return tuple(value for value in self.anc_levels if value in (3, 4))
        return ()

    def slider_levels(self, mode):
        special = self.special_levels(mode)
        return tuple(value for value in self.levels(mode) if value not in special)

    def level_label_key(self, mode, value):
        if value not in self.levels(mode):
            return None
        if mode == 1 and self.anc_schema == "discrete_legacy":
            return ANC_LEVEL_LABELS.get(value)
        if mode == 2 and self.transparency_schema == "discrete_legacy":
            return TRANSPARENCY_LEVEL_LABELS.get(value)
        return None


def noise_capabilities(caps):
    """Base catalog gears only; unknown firmware cannot enable OTA gears."""
    anc = next((fid for fid in ANC_FUNCTIONS if fid in caps.functions), None)
    trans = next((fid for fid in TRANSPARENCY_FUNCTIONS if fid in caps.functions), None)

    def gears(fid):
        values = caps.options.get(fid, {}).get("tws_gear", [])
        if not isinstance(values, list):
            return ()
        return tuple(dict.fromkeys(v for v in values if type(v) is int and 0 <= v <= 255))

    options = caps.options.get(anc, {})
    code = caps.model.rsplit(".", 1)[-1].casefold()
    adaptive = "level" if anc and any(code == old or code == old + "g" for old in OLD_ADAPTIVE_MODELS) else (
        "switch" if anc and options.get("auto_fit") == 1 else None)
    wear = options.get("anc_wear_type")
    anc_levels, trans_levels = gears(anc), gears(trans)
    anc_schema = "unknown"
    if caps.model == SPECIAL_ANC_MODEL:
        anc_schema = "l71_special"
    elif anc_levels == tuple(range(20)):
        anc_schema = "multilevel_20"
    elif anc_levels and all(v in ANC_LEVEL_LABELS for v in anc_levels):
        anc_schema = "discrete_legacy"
    trans_schema = ("discrete_legacy" if trans_levels
                    and all(v in TRANSPARENCY_LEVEL_LABELS for v in trans_levels) else "unknown")
    return NoiseCapabilities((0,) + ((1,) if anc else ()) + ((2,) if trans else ())
                             if anc or trans else (), anc_levels, trans_levels, adaptive,
                             wear if type(wear) is int and wear in (1, 2, 3) else None,
                             anc_schema, trans_schema)


@dataclass(frozen=True)
class NoiseState:
    mode: int
    level: int | None = None
    extra: bytes = b""


def build_noise_mode(counter, mode):
    if type(mode) is not int or mode not in (0, 1, 2):
        raise ValueError("Unknown noise mode")
    return _frame(0x08, counter, bytes((2, 4, mode)))


def build_noise_level(counter, mode, level, supported_levels):
    if (type(mode) is not int or mode not in (1, 2) or type(level) is not int
            or not 0 <= level <= 255 or level not in supported_levels):
        raise ValueError("Unsupported noise level")
    return _frame(0xF2, counter, bytes((4, 0, 11, mode, level)))


def build_noise_read(counter):
    return _frame(0xF3, counter, bytes.fromhex("00 0b"))


def parse_noise_state(data):
    value = _records(data).get(11)
    if value is None or len(value) < 2:
        raise ValueError("Missing or truncated noise state")
    return NoiseState(value[0], value[1], value[2:])


def _records(data):
    # The shared parser has no FF/0034 extended-length support yet. Fail closed
    # instead of interpreting its marker as a normal 255-byte record.
    pos = 0
    while pos < len(data):
        if data[pos] == 255:
            raise ValueError("Extended CommonConfig records are not supported")
        pos += 1 + data[pos]
    return parse_config_records(data)


def parse_noise_notification(packet):
    """F4 uses request SEQ or response STATUS/SEQ, never ACK state."""
    if packet.opcode != 0xF4:
        return None
    offset = 1 if packet.flags & 0x80 else 2
    if len(packet.payload) < offset or (offset == 2 and packet.payload[0]):
        return None
    records = _records(packet.payload[offset:])
    return parse_noise_state(packet.payload[offset:]) if 11 in records else None
