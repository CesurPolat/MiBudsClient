"""Serialized ANC writes followed by authoritative device readback."""
from .noise import build_noise_mode, build_noise_level, build_noise_read, parse_noise_state


class NoiseTransport:
    def __init__(self, channel):
        self.channel = channel

    def read(self, session, timeout=2.0):
        return parse_noise_state(self.channel.exchange(
            0xF3, build_noise_read, timeout, session, 11, namespace="noise"))

    def apply(self, capabilities, session, mode, level=None, timeout=2.0):
        if type(mode) is not int or mode not in capabilities.modes:
            raise ValueError("Unsupported noise mode")
        builder = lambda ss: build_noise_mode(ss, mode)
        opcode = 0x08
        if level is not None:
            # Validate before any transport activity.
            build_noise_level(0, mode, level, capabilities.levels(mode))
            builder = lambda ss: build_noise_level(ss, mode, level, capabilities.levels(mode))
            opcode = 0xF2
        with self.channel.transaction():
            # ACK rawData is not CommonConfig and is never reported as state.
            self.channel.exchange(opcode, builder, timeout, session, None, namespace="noise")
            actual = self.read(session, timeout)
            if actual.mode != mode or (level is not None and actual.level != level):
                raise ValueError("Device readback does not match the requested noise setting")
            return actual
