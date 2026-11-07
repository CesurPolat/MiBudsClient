"""Game mode config 002F; the shared listener owns all socket reads."""
from utils.i18n import message as m

from .config_transport import parse_config_records


class LatencyTransport:
    def __init__(self, channel):
        self.channel = channel
        self._confirmed = (None, None)

    @property
    def state(self):
        session, value = self._confirmed
        return value if session == self.channel.generation else None

    def _exchange(self, opcode, builder, timeout, session):
        return self.channel.exchange(opcode, builder, timeout, session, 0x002F,
                                     namespace="latency")

    def read(self, timeout=5.0, session=None):
        session = self.channel.generation if session is None else session
        with self.channel.transaction():
            self._confirmed = (session, None)
            data = self._exchange(0xF3, lambda counter: bytes.fromhex(
                f"fe dc ba c4 f3 00 03 {counter:02x} 00 2f ef"), timeout, session)
            value = parse_config_records(data).get(0x002F)
            if value not in (bytes.fromhex("00"), bytes.fromhex("01")):
                raise ValueError(m("latency.unknown"))
            if session != self.channel.generation:
                raise ConnectionError(m("latency.connection_changed"))
            actual = value == bytes.fromhex("01")
            self._confirmed = (session, actual)
            return actual

    def write(self, enabled, timeout=5.0):
        session = self.channel.generation
        with self.channel.transaction():
            self._confirmed = (session, None)
            self._exchange(0xF2, lambda counter: bytes.fromhex(
                f"fe dc ba c4 f2 00 05 {counter:02x} 03 00 2f {int(enabled):02x} ef"),
                timeout, session)
            # An ACK confirms the write request, never the resulting mode.
            actual = self.read(timeout, session)
            if actual != enabled:
                raise ValueError(m("latency.unconfirmed"))
            return actual
