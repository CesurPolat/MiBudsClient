"""Shared serialized RCSP config transactions; only the listener receives bytes."""

from utils.i18n import message as m

import threading
from dataclasses import dataclass

from .rcsp import RcspStreamParser


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

    @property
    def generation(self):
        with self._condition:
            return self._generation

    def reset(self, reason):
        with self._condition:
            self._generation += 1
            self._last_read = None
            self._parser.reset()
            if self._pending is not None:
                self._pending.error = reason
                self._pending.completed = True
            self._condition.notify_all()

    def feed(self, data):
        matched = False
        with self._condition:
            for packet in self._parser.feed(data):
                request = self._pending
                # Bit 7 indicates a command; only consume responses.
                if (request is None or request.completed or packet.flags & 0x80
                        or packet.opcode != request.opcode or len(packet.payload) < 2):
                    continue
                status, counter = packet.payload[:2]
                if counter != request.counter:
                    continue
                if not status and request.config_id is not None and packet.payload[2:]:
                    try:
                        records = parse_config_records(packet.payload[2:])
                    except ValueError as exc:
                        request.error = str(exc)
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

    def _exchange(self, opcode, builder, timeout, generation, config_id=None, namespace="gesture"):
        with self._condition:
            if generation != self._generation or not self._connection.connected:
                raise ConnectionError(m(namespace + ".disconnected"))
            counter = self._counter
            self._counter = (counter + 1) & 255
            # The legacy latency command always uses 0x90 with opcode F2.
            if self._counter == 0x90:
                self._counter = 0x91
            request = _Request(opcode, counter, config_id=config_id, namespace=namespace)
            self._parser.reset()
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
        end = pos + 1 + length
        if length < 2 or end > len(data):
            raise ValueError(m("eq.invalid"))
        config = int.from_bytes(data[pos + 1:pos + 3], "big")
        if config in records:
            raise ValueError(m("eq.invalid"))
        records[config] = data[pos + 3:end]
        pos = end
    return records
