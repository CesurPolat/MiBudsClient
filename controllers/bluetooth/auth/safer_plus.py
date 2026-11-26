"""SAFER+ variant used by Xiaomi/Redmi Buds to authenticate the app (128-bit key, 8 rounds).

Interoperability implementation written from the protocol notes of Gadgetbridge
(AGPL-3.0, Redmi Buds support) and the MIT-licensed XiaomayEarbudsWin port. Validated
against real Redmi Buds 5 Pro hardware (see tests/test_safer_plus.py).
"""

# Vendored unchanged algorithm from LeandroPG19/Buds, commit
# e7e25b084114932ca962a61b35a37e5237702154, bluetooth/safer_plus.py.
# Upstream repository license: GNU GPL v3; see
# the repository LICENSE and docs/command-auth.md.
# The hardware validation statement above is upstream's, not this project's.

BLOCK_SIZE = 16

# Bit i set -> byte i uses XOR (and the exp table); clear -> modular add (and the log table).
_PATTERN = 0x9999

# Fixed 16-byte block the earbuds expect to see encrypted under their own challenge.
SEQ = bytes([0x11, 0x22, 0x33, 0x33, 0x22, 0x11, 0x11, 0x22, 0x33, 0x33, 0x22, 0x11, 0x11, 0x22, 0x33, 0x33])

_COEFFICIENTS = (
    (2, 1, 1, 1, 4, 2, 1, 1, 2, 2, 4, 2, 4, 4, 16, 8),
    (2, 1, 1, 1, 4, 2, 1, 1, 1, 1, 2, 1, 2, 2, 8, 4),
    (1, 1, 4, 2, 2, 2, 4, 2, 16, 8, 4, 4, 2, 1, 1, 1),
    (1, 1, 4, 2, 1, 1, 2, 1, 8, 4, 2, 2, 2, 1, 1, 1),
    (16, 8, 2, 2, 4, 2, 4, 4, 1, 1, 4, 2, 1, 1, 2, 1),
    (8, 4, 1, 1, 2, 1, 2, 2, 1, 1, 4, 2, 1, 1, 2, 1),
    (2, 2, 4, 2, 4, 4, 16, 8, 2, 1, 1, 1, 4, 2, 1, 1),
    (1, 1, 2, 1, 2, 2, 8, 4, 2, 1, 1, 1, 4, 2, 1, 1),
    (4, 2, 4, 4, 16, 8, 2, 2, 1, 1, 2, 1, 1, 1, 4, 2),
    (2, 1, 2, 2, 8, 4, 1, 1, 1, 1, 2, 1, 1, 1, 4, 2),
    (4, 4, 16, 8, 1, 1, 2, 1, 4, 2, 1, 1, 4, 2, 2, 2),
    (2, 2, 8, 4, 1, 1, 2, 1, 4, 2, 1, 1, 2, 1, 1, 1),
    (1, 1, 2, 1, 1, 1, 4, 2, 4, 4, 16, 8, 2, 2, 4, 2),
    (1, 1, 2, 1, 1, 1, 4, 2, 2, 2, 8, 4, 1, 1, 2, 1),
    (4, 2, 1, 1, 2, 1, 1, 1, 4, 2, 2, 2, 16, 8, 4, 4),
    (4, 2, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 8, 4, 2, 2),
)

_EXP = tuple(0 if i == 128 else pow(45, i, 257) % 256 for i in range(256))


def _build_log() -> tuple[int, ...]:
    # log(0) = 128 and log(1) = 0, the inverse of exp (45**128 wraps to 0).
    log = [0] * 256
    log[0] = 128
    for i in range(1, 256):
        value = pow(45, i, 257)
        if value != 256:
            log[value] = i % 256
    return tuple(log)


_LOG = _build_log()

_BIAS = tuple(
    tuple(pow(45, pow(45, 17 * (i + 2) + (j + 1), 257), 257) % 256 for j in range(BLOCK_SIZE))
    for i in range(BLOCK_SIZE)
)


def _xor_bit(i: int) -> bool:
    return bool(_PATTERN & (1 << i))


def _rotate_left_3(value: int) -> int:
    return ((value << 3) | (value >> 5)) & 0xFF


def _key_schedule(key: bytes) -> list[list[int]]:
    first = list(key)
    first[15] ^= 6

    register = first + [0]
    for byte in first:
        register[16] ^= byte

    keys = [first]
    for key_index in range(1, 17):
        register = [_rotate_left_3(b) for b in register]
        keys.append([(register[(key_index + i) % 17] + _BIAS[key_index - 1][i]) & 0xFF for i in range(BLOCK_SIZE)])
    return keys


def _combine(value: int, other: int, i: int) -> int:
    return (value ^ other) if _xor_bit(i) else (value + other) & 0xFF


def encrypt(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt one 16-byte block with a 16-byte key."""
    if len(plaintext) != BLOCK_SIZE or len(key) != BLOCK_SIZE:
        raise ValueError("SAFER+ works on 16-byte blocks and 16-byte keys")

    keys = _key_schedule(key)
    block = list(plaintext)

    for round_index in range(8):
        if round_index == 2:
            block = [_combine(block[i], plaintext[i], i) for i in range(BLOCK_SIZE)]

        block = [_combine(block[i], keys[2 * round_index][i], i) for i in range(BLOCK_SIZE)]
        block = [_EXP[b] if _xor_bit(i) else _LOG[b] for i, b in enumerate(block)]
        block = [
            (keys[2 * round_index + 1][i] + b) & 0xFF if _xor_bit(i) else keys[2 * round_index + 1][i] ^ b
            for i, b in enumerate(block)
        ]
        block = [sum(_COEFFICIENTS[i][j] * block[j] for j in range(BLOCK_SIZE)) & 0xFF for i in range(BLOCK_SIZE)]

    block = [keys[16][i] ^ b if _xor_bit(i) else (keys[16][i] + b) & 0xFF for i, b in enumerate(block)]
    return bytes(block)


def challenge_response(challenge: bytes) -> bytes:
    """Answer to a 16-byte challenge sent by the earbuds."""
    return encrypt(SEQ, challenge)
