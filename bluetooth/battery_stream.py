"""Reassemble the existing battery records across RFCOMM receives."""

import threading

from .constants import BATTERY_PATTERN
from .protocol import BudsProtocol


class BatteryStreamParser:
    """Keep partial records and consume every complete record exactly once."""

    def __init__(self):
        self._buffer = bytearray()
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._buffer.clear()

    def feed(self, data: bytes):
        with self._lock:
            self._buffer.extend(data)
            records = []
            record_size = len(BATTERY_PATTERN) + 3
            while self._buffer:
                start = self._buffer.find(BATTERY_PATTERN)
                if start < 0:
                    # Preserve only a possible split pattern, bounding stream noise.
                    self._buffer[:] = self._buffer[-(len(BATTERY_PATTERN) - 1):]
                    break
                if start:
                    del self._buffer[:start]
                if len(self._buffer) < record_size:
                    break
                status = BudsProtocol.parse_battery(bytes(self._buffer[:record_size]))
                if status is not None:
                    records.append(status)
                del self._buffer[:record_size]
            return records
