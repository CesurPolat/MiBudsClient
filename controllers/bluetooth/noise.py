"""ANC codec and function-list capabilities; not hardware certification."""
from dataclasses import dataclass

from .config_transport import parse_config_records
from .equalizer import _frame


VALIDATED_NOISE_MODELS = frozenset()
ANC_FUNCTIONS = (1002, 1003, 1006, 1007)
TRANSPARENCY_FUNCTIONS = (1004, 1005)
OLD_ADAPTIVE_MODELS = frozenset(("l76", "l77", "k73", "k73a", "l77s"))


def noise_backend_enabled(caps):
    """Expose noise controls when the device function list supports a mode."""
    return bool(noise_capabilities(caps).modes)


@dataclass(frozen=True)
class NoiseCapabilities:
    modes: tuple = ()
    anc_levels: tuple = ()
    transparency_levels: tuple = ()
    adaptive: str | None = None
    wear_type: int | None = None

    def levels(self, mode):
        return self.anc_levels if mode == 1 else self.transparency_levels if mode == 2 else ()


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
    return NoiseCapabilities((0,) + ((1,) if anc else ()) + ((2,) if trans else ())
                             if anc or trans else (), gears(anc), gears(trans), adaptive,
                             wear if type(wear) is int and wear in (1, 2, 3) else None)


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
