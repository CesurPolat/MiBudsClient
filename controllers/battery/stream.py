"""Battery telemetry from complete target-info and status RCSP frames."""
import threading

from ..bluetooth.packets.rcsp import RcspStreamParser, is_supported_target, parse_info_fields
from ..bluetooth.packets.protocol import BatteryStatus


BATTERY_UNKNOWN = 0xFF
BATTERY_CHARGING_OFFSET = 128


def battery_state(raw) -> tuple[int, bool] | None:
    """Return (percent, charging) only for a valid byte with a 0–100 level."""
    if type(raw) is not int or not 0 <= raw < BATTERY_UNKNOWN:
        return None
    charging = raw >= BATTERY_CHARGING_OFFSET
    percent = raw - BATTERY_CHARGING_OFFSET if charging else raw
    return (percent, charging) if percent <= 100 else None


class BatteryStreamParser:
    def __init__(self):
        self._parser = RcspStreamParser()
        self._lock = threading.Lock()
        self._values = [BATTERY_UNKNOWN] * 3

    def reset(self):
        with self._lock:
            self._parser.reset()
            self._values = [BATTERY_UNKNOWN] * 3

    def feed(self, data):
        return self.feed_packets(self._parser.feed(data))

    def feed_packets(self, packets):
        statuses = []
        with self._lock:
            for packet in packets:
                if not is_supported_target(packet.flags):
                    continue
                if packet.opcode == 0x02 and not packet.flags & 0x80:
                    if len(packet.payload) < 2 or packet.payload[0]:
                        continue
                    data, kind = packet.payload[2:], 7
                elif packet.opcode == 0x0E and packet.flags & 0x80:
                    if not packet.payload:
                        continue
                    data, kind = packet.payload[1:], 0
                else:
                    continue
                try:
                    values = parse_info_fields(data).get(kind)
                except ValueError:
                    continue
                if values is None or not 1 <= len(values) <= 3:
                    continue
                if any(value != BATTERY_UNKNOWN and battery_state(value) is None for value in values):
                    continue
                # Omitted components retain their last value; FF explicitly
                # means unknown, and zero is a valid empty battery.
                self._values[:len(values)] = values
                statuses.append(BatteryStatus(*self._values))
        return statuses
