"""Length-framed RCSP target-info queries and device identity decoding."""

from dataclasses import dataclass
from typing import Optional

from .device_catalog import get_device_codes, get_device_name, get_device_models



@dataclass(frozen=True)
class DeviceIdentity:
    """Model lookup keys reported by the device, not a model name."""

    vid: int
    pid: int

    @property
    def model_name(self) -> Optional[str]:
        return get_device_name(self.vid, self.pid)

    @property
    def model_codes(self) -> tuple[str, ...]:
        return get_device_codes(self.vid, self.pid)

    @property
    def models(self) -> tuple[dict, ...]:
        """Complete app records (func_list, extra_info, icons, etc.) for this ID."""
        return get_device_models(self.vid, self.pid)

    def describe(self) -> str:
        model = self.model_name or "Unknown model"
        if self.model_codes:
            model += f" [{', '.join(self.model_codes)}]"
        return f"{model} / VID: 0x{self.vid:04X} / PID: 0x{self.pid:04X}"


@dataclass(frozen=True)
class RcspPacket:
    flags: int
    opcode: int
    payload: bytes


def build_identity_request(counter: int) -> bytes:
    """GetTargetInfo with all fields requested and a caller-owned counter."""
    if not 0 <= counter <= 0xFF:
        raise ValueError("RCSP counter must fit in one byte")
    return bytes.fromhex(f"fe dc ba c4 02 00 05 {counter:02x} ff ff ff ff ef")


def parse_identity_fields(fields: bytes) -> Optional[DeviceIdentity]:
    """Decode type 03 only after validating the entire TLV field list."""
    pos = 0
    identity = None
    while pos < len(fields):
        length = fields[pos]
        end = pos + 1 + length
        if length < 1 or end > len(fields):
            return None
        if fields[pos + 1] == 0x03:
            value = fields[pos + 2:end]
            if len(value) != 4 or identity is not None:
                return None
            identity = DeviceIdentity(
                vid=int.from_bytes(value[:2], "big"),
                pid=int.from_bytes(value[2:], "big"),
            )
        pos = end
    return identity


class RcspStreamParser:
    """Reassemble fragmented/coalesced recv data using the RCSP payload length."""

    _HEADER = bytes.fromhex("fe dc ba")

    def __init__(self):
        self._buffer = bytearray()

    def reset(self) -> None:
        self._buffer.clear()

    def feed(self, data: bytes) -> list[RcspPacket]:
        self._buffer.extend(data)
        packets = []
        while self._buffer:
            start = self._buffer.find(self._HEADER)
            if start < 0:
                # Keep a possible split header; discard unrelated stream noise.
                self._buffer[:] = self._buffer[-2:]
                break
            if start:
                del self._buffer[:start]
            if len(self._buffer) < 7:
                break
            payload_length = int.from_bytes(self._buffer[5:7], "big")
            frame_length = 8 + payload_length
            if len(self._buffer) < frame_length:
                break
            if self._buffer[frame_length - 1] != 0xEF:
                del self._buffer[0]
                continue
            packets.append(RcspPacket(
                flags=self._buffer[3],
                opcode=self._buffer[4],
                payload=bytes(self._buffer[7:frame_length - 1]),
            ))
            del self._buffer[:frame_length]
        return packets
