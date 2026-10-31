"""RCSP command-auth framing, separate from the cipher and session policy."""
from dataclasses import dataclass

from .rcsp import RcspPacket


@dataclass(frozen=True)
class AuthFrame:
    request: bool
    opcode: int
    sequence: int
    data: bytes
    status: int = 0


def decode_auth(packet: RcspPacket) -> AuthFrame | None:
    if packet.opcode not in (0x50, 0x51) or packet.flags & 7 not in (4, 7):
        return None
    request = bool(packet.flags & 0x80)
    minimum = 1 if request else 2
    if len(packet.payload) < minimum:
        raise ValueError("Truncated auth frame")
    status = 0 if request else packet.payload[0]
    sequence = packet.payload[0 if request else 1]
    return AuthFrame(request, packet.opcode, sequence, packet.payload[minimum:], status)


def encode_auth(opcode: int, sequence: int, data: bytes, *, request=True, status=0) -> bytes:
    if opcode not in (0x50, 0x51) or not 0 <= sequence <= 255 or not 0 <= status <= 255:
        raise ValueError("Invalid auth frame fields")
    # Role 4 is this application's targetApp, including replies to peer requests.
    flags = 0xC4 if request else 0x04
    body = bytes([sequence]) + data if request else bytes([status, sequence]) + data
    return bytes.fromhex("fe dc ba") + bytes([flags, opcode]) + len(body).to_bytes(2, "big") + body + bytes.fromhex("ef")
