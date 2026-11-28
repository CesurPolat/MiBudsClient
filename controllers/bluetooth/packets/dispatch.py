"""Distribute complete RCSP packets from the Bluetooth session's sole reader."""

from ...battery.stream import BatteryStreamParser
from ...gestures.protocol import parse_gesture_records
from ...noise.capture import record
from ...noise.protocol import parse_noise_notification
from ..auth.auth_session import CommandAuthSession
from .config_transport import parse_config_records
from .rcsp import RcspStreamParser, is_supported_target, parse_info_fields


class PacketDispatcher:
    def __init__(self, *, gestures, equalizer, latency, noise, capture_noise,
                 on_identity, on_battery, on_noise, on_config):
        self._gestures = gestures
        self._equalizer = equalizer
        self._latency = latency
        self._noise = noise
        self._capture_noise = capture_noise
        self._on_identity = on_identity
        self._on_battery = on_battery
        self._on_noise = on_noise
        self._on_config = on_config
        self._parser = RcspStreamParser()
        self._battery_parser = BatteryStreamParser()

    def reset(self):
        self._battery_parser.reset()
        self._parser.reset()

    def feed(self, data, *, connection, session) -> bool:
        """Dispatch a chunk and report battery data or a matched config response."""
        packets = self._parser.feed(data)
        self._on_identity(packets)
        config_response = self._gestures.feed_packets(packets)
        statuses = self._battery_parser.feed_packets(packets)
        capture_noise = self._capture_noise()
        for packet in packets:
            if packet.opcode in (0x50, 0x51):
                auth = connection.auth_session
                if isinstance(auth, CommandAuthSession) and auth.authenticated:
                    auth.feed(bytes.fromhex(packet.raw_hex))
                continue
            if capture_noise:
                record("RX", bytes.fromhex(packet.raw_hex))
            if not is_supported_target(packet.flags):
                continue
            if packet.opcode == 0xF4:
                offset = 1 if packet.flags & 0x80 else 2
                if len(packet.payload) < offset or (offset == 2 and packet.payload[0]):
                    continue
                try:
                    records = parse_config_records(packet.payload[offset:])
                except ValueError:
                    continue
                self._gestures.notify(session, records)
                self._latency.notify(session, records)
                eq = self._equalizer.notify(session, records)
                if 2 in records or 80 in records:
                    try:
                        self._gestures._last_read = parse_gesture_records(packet.payload[offset:], physical=True)
                    except ValueError:
                        pass
                self._noise.notify_aux(session, records)
                try:
                    state = parse_noise_notification(packet)
                except ValueError:
                    state = None
                if state is not None:
                    state = self._noise.enrich(session, state)
                    self._noise.notify(session, state)
                    self._on_noise(session, state)
                elif 12 in records or 37 in records:
                    state = self._noise.current_state(session)
                    if state is not None:
                        self._on_noise(session, state)
                self._on_config(session, records, eq)
            elif packet.opcode == 0x0E:
                try:
                    if not packet.flags & 0x80 or not packet.payload:
                        continue
                    parse_info_fields(packet.payload[1:])
                except ValueError:
                    continue
            else:
                continue
            # A single router owns notification ACKs. Bit 6 requests one.
            if packet.flags & 0x80 and packet.flags & 0x40:
                connection.send(bytes.fromhex("fe dc ba 04") +
                                      bytes((packet.opcode, 0, 2, 0, packet.payload[0], 0xEF)))

        if statuses:
            self._on_battery(statuses)
        return bool(statuses or config_response)
