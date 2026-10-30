"""Redmi Buds 6 Play EQ config codec. Requires hardware validation."""
from dataclasses import dataclass

from utils.i18n import message as m
from .config_transport import parse_config_records


PROFILE_KEYS = {0: "balanced", 1: "vocal", 5: "bass", 6: "treble", 7: "volume"}


@dataclass(frozen=True)
class EqBand:
    frequency: int
    gain: int


@dataclass(frozen=True)
class CustomEq:
    mode: int
    bound: int
    minimum: int
    eq_id: int
    name: bytes
    bands: tuple[EqBand, ...]


@dataclass(frozen=True)
class EqState:
    profile: int | None = None
    custom: CustomEq | None = None


@dataclass
class EqResult:
    success: bool
    state: EqState | None = None
    message: str = ""


def eq_profiles(device_name, identity=None):
    from .capabilities import resolve_capabilities
    caps = resolve_capabilities(device_name, identity)
    return caps.profiles if caps.supports("eq") else ()


def _frame(opcode, counter, payload):
    if type(counter) is not int or not 0 <= counter <= 255:
        raise ValueError("RCSP counter must fit in one byte")
    body = bytes([counter]) + payload
    return bytes.fromhex(f"fe dc ba c4 {opcode:02x} {len(body):04x}") + body + bytes.fromhex("ef")


def build_eq_request(counter, config):
    if config not in (7, 55):
        raise ValueError(m("eq.invalid"))
    return _frame(0xF3, counter, config.to_bytes(2, "big"))


def _write(counter, config, value):
    length = 2 + len(value)
    if length > 255:
        raise ValueError(m("eq.invalid"))
    return _frame(0xF2, counter, bytes([length]) + config.to_bytes(2, "big") + value)


def build_profile(counter, profile):
    if type(profile) is not int or profile not in PROFILE_KEYS:
        raise ValueError(m("eq.unsupported"))
    return _write(counter, 7, bytes([profile]))


def build_custom_mode(counter, mode):
    if type(mode) is not int or mode not in (*PROFILE_KEYS, 10):
        raise ValueError(m("eq.unsupported"))
    return _write(counter, 55, bytes([1, mode]))


def build_custom_eq(counter, bands, bound, *, preview=False):
    if not bands or type(bound) is not int or not 1 <= bound <= 127:
        raise ValueError(m("eq.invalid"))
    # Save has the larger record; require every editable curve to fit both operations.
    # FF is reserved for the special extended-length config format (type 0034).
    if 9 + 3 * len(bands) >= 255:
        raise ValueError(m("eq.invalid"))
    value = bytes.fromhex("05 01 01") if preview else bytes.fromhex("01 0a 01 01 01 00")
    value += bytes([len(bands)])
    for band in bands:
        if (type(band.frequency) is not int or not 1 <= band.frequency <= 65535
                or type(band.gain) is not int or not -bound <= band.gain <= bound):
            raise ValueError(m("eq.invalid"))
        value += band.frequency.to_bytes(2, "big") + bytes([
            band.gain if band.gain >= 0 else 128 - band.gain])
    return _write(counter, 55, value)


def build_eq_reset(counter):
    return _write(counter, 55, bytes.fromhex("04 01 01 01"))


def parse_profile(data):
    value = parse_config_records(data).get(7)
    if value is None or len(value) != 1:
        raise ValueError(m("eq.invalid"))
    return value[0]


def parse_custom_eq(data):
    value = parse_config_records(data).get(55)
    if value is None or len(value) < 7 or value[0] != 1 or value[4] != 1:
        raise ValueError(m("eq.invalid"))
    offset = 6 + value[5]
    if offset >= len(value):
        raise ValueError(m("eq.invalid"))
    count = value[offset]
    bound = value[2] or 10
    if not count or count > 81 or bound > 127 or len(value) != offset + 1 + 3 * count:
        raise ValueError(m("eq.invalid"))
    bands = []
    for pos in range(offset + 1, len(value), 3):
        frequency = int.from_bytes(value[pos:pos + 2], "big")
        gain = value[pos + 2]
        gain = gain if gain < 128 else 128 - gain
        if not frequency or abs(gain) > bound:
            raise ValueError(m("eq.invalid"))
        bands.append(EqBand(frequency, gain))
    return CustomEq(value[1], bound, value[3], value[4], value[6:offset], tuple(bands))
