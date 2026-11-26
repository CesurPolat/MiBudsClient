"""Shared serialized RCSP config transactions; only the listener receives bytes."""

from utils.app.i18n import message as m

import threading
import time
from dataclasses import dataclass

from .rcsp import RcspStreamParser, is_supported_target


@dataclass
class _Request:
    opcode: int
    counter: int
    completed: bool = False
    error: str = ""
    data: bytes = b""
    config_id: int | None = None
    namespace: str = "gesture"


class RcspConfigTransport:
    def __init__(self, connection):
        self._connection = connection
        self._serial = threading.RLock()
        self._condition = threading.Condition()
        self._parser = RcspStreamParser()
        self._counter = 0xA0
        self._generation = 0
        self._pending = None
        self._last_read = None
        self._values = {}
        self._revision = 0

    @property
    def generation(self):
        with self._condition:
            return self._generation

    def reset(self, reason):
        with self._condition:
            self._generation += 1
            self._last_read = None
            self._values.clear()
            self._revision += 1
            self._parser.reset()
            if self._pending is not None:
                self._pending.error = reason
                self._pending.completed = True
            self._condition.notify_all()

    def feed(self, data):
        return self.feed_packets(self._parser.feed(data))

    def feed_packets(self, packets):
        matched = False
        with self._condition:
            for packet in packets:
                request = self._pending
                # Bit 7 indicates a command; only consume responses.
                if (request is None or request.completed or packet.flags & 0x80
                        or not is_supported_target(packet.flags)
                        or packet.opcode != request.opcode or len(packet.payload) < 2):
                    continue
                status, counter = packet.payload[:2]
                if counter != request.counter:
                    continue
                if not status and request.opcode == 0xF3 and request.config_id is not None and packet.payload[2:]:
                    try:
                        records = parse_config_records(packet.payload[2:])
                    except ValueError as exc:
                        request.error = (m("latency.invalid") if request.namespace == "latency"
                                         else str(exc))
                        request.completed = True
                        self._condition.notify_all()
                        matched = True
                        continue
                    if request.config_id not in records:
                        continue
                elif not status and request.opcode == 0xF3 and request.config_id is not None:
                    continue
                matched = True
                request.error = m(request.namespace + ".rejected", code=f"{status:02X}") if status else ""
                request.data = packet.payload[2:]
                request.completed = True
                self._condition.notify_all()
        return matched

    def notify(self, generation, records):
        with self._condition:
            if generation != self._generation:
                return
            self._revision += 1
            for config, value in records.items():
                self._values[config] = (self._revision, value)
            self._condition.notify_all()

    @property
    def revision(self):
        with self._condition:
            return self._revision

    def confirm(self, config, parser, read, matches, timeout, generation, revision, namespace="eq"):
        """Read/await fresh notifications after one write, within a fixed budget.

        Return the last actual value as well as confirmation; an ACK is never
        substituted for device state. Reset wakes waits and cancels old sessions.
        """
        deadline = time.monotonic() + timeout
        actual = None
        while True:
            with self._condition:
                if generation != self._generation or not self._connection.connected:
                    raise ConnectionError(m(namespace + ".connection_changed"))
                cached = self._values.get(config)
                if cached is not None and cached[0] > revision:
                    actual = parser(bytes([len(cached[1]) + 2]) + config.to_bytes(2, "big") + cached[1])
                    if matches(actual):
                        return True, actual
                revision = self._revision
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False, actual
            try:
                actual = read(min(0.4, remaining))
            except TimeoutError:
                pass
            else:
                if generation != self.generation:
                    raise ConnectionError(m(namespace + ".connection_changed"))
                if time.monotonic() <= deadline and matches(actual):
                    return True, actual
            with self._condition:
                self._condition.wait_for(
                    lambda: generation != self._generation or self._revision != revision,
                    min(0.2, max(0, deadline - time.monotonic())))

    def _exchange(self, opcode, builder, timeout, generation, config_id=None, namespace="gesture"):
        with self._condition:
            if generation != self._generation or not self._connection.connected:
                raise ConnectionError(m(namespace + ".disconnected"))
            counter = self._counter
            self._counter = (counter + 1) & 255
            # Reserve the counter used by the legacy mode-packet helper.
            if self._counter == 0x90:
                self._counter = 0x91
            request = _Request(opcode, counter, config_id=config_id, namespace=namespace)
            self._pending = request
            try:
                self._connection.send(builder(counter))
                if not self._condition.wait_for(lambda: request.completed, timeout):
                    raise TimeoutError(m(namespace + ".timeout"))
                if request.error:
                    raise ConnectionError(request.error)
                if generation != self._generation:
                    raise ConnectionError(m(namespace + ".connection_changed"))
                return request.data
            finally:
                self._pending = None

    def transaction(self):
        return self._serial

    def exchange(self, opcode, builder, timeout, generation, config_id, namespace="eq"):
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        with self._serial:
            return self._exchange(opcode, builder, timeout, generation, config_id, namespace)


def parse_config_records(data):
    """Validate complete length-prefixed config records, including duplicates."""
    records = {}
    pos = 0
    while pos < len(data):
        length = data[pos]
        if pos + 3 > len(data):
            raise ValueError(m("eq.invalid"))
        config = int.from_bytes(data[pos + 1:pos + 3], "big")
        if length == 255:
            # APK CommonConfig: FF/0034 carries a big-endian value length.
            # Unknown extended types have no safe boundary; never byte-scan.
            if config != 0x0034 or pos + 5 > len(data):
                raise ValueError(m("eq.invalid"))
            end = pos + 5 + int.from_bytes(data[pos + 3:pos + 5], "big")
        else:
            end = pos + 1 + length
        if length < 2 or end > len(data):
            raise ValueError(m("eq.invalid"))
        if config in records:
            raise ValueError(m("eq.invalid"))
        records[config] = data[pos + 3:end]
        pos = end
    return records
