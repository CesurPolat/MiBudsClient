"""Serialized gesture transactions, fed exclusively by the existing listener."""

import threading
from dataclasses import dataclass

from .gestures import (
    GestureResult, build_gesture_assignment, build_gesture_request,
    parse_gesture_records,
)
from .rcsp import RcspStreamParser


@dataclass
class _Request:
    opcode: int
    counter: int
    completed: bool = False
    error: str = ""
    data: bytes = b""


class GestureTransport:
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
                matched = True
                request.error = f"Gesture request rejected (status 0x{status:02X})." if status else ""
                request.data = packet.payload[2:]
                request.completed = True
                self._condition.notify_all()
        return matched

    def _exchange(self, opcode, builder, timeout, generation):
        with self._condition:
            if generation != self._generation or not self._connection.connected:
                raise ConnectionError("Earbuds disconnected. Refresh to read settings again.")
            counter = self._counter
            self._counter = (counter + 1) & 255
            # The legacy latency command always uses 0x90 with opcode F2.
            if self._counter == 0x90:
                self._counter = 0x91
            request = _Request(opcode, counter)
            self._parser.reset()
            self._pending = request
            try:
                self._connection.send(builder(counter))
                if not self._condition.wait_for(lambda: request.completed, timeout):
                    raise TimeoutError("Gesture request timed out. Refresh to try again.")
                if request.error:
                    raise ConnectionError(request.error)
                if generation != self._generation:
                    raise ConnectionError("Connection changed during gesture request.")
                return request.data
            finally:
                self._pending = None

    def read(self, timeout=5.0, generation=None):
        if timeout <= 0:
            raise ValueError("Gesture timeout must be positive")
        generation = self.generation if generation is None else generation
        with self._serial:
            try:
                data = self._exchange(0xF3, build_gesture_request, timeout, generation)
                assignments = parse_gesture_records(data)
                with self._condition:
                    if generation != self._generation:
                        raise ConnectionError("Connection changed during gesture request.")
                    self._last_read = dict(assignments)
                return GestureResult(True, assignments, "Gesture settings loaded.")
            except (OSError, ValueError) as exc:
                self._last_read = None
                return GestureResult(False, message=str(exc))

    def write(self, gesture_type, side, action, timeout=5.0, generation=None):
        if timeout <= 0:
            raise ValueError("Gesture timeout must be positive")
        generation = self.generation if generation is None else generation
        with self._serial:
            try:
                with self._condition:
                    if self._last_read is None or gesture_type not in self._last_read:
                        raise ValueError("Refresh gesture settings before changing this assignment.")
                    self._last_read = None
                self._exchange(0xF2, lambda counter: build_gesture_assignment(
                    counter, gesture_type, side, action), timeout, generation)
                result = self.read(timeout, generation)
                if not result.success:
                    return GestureResult(False, message=f"Write sent; verification failed: {result.message}")
                actual = result.assignments.get(gesture_type)
                if actual is None or actual[0 if side == "left" else 1] != action:
                    self._last_read = None
                    return GestureResult(False, message="The earbuds did not confirm this assignment. Refresh to read current settings.")
                result.message = "Gesture assignment saved and verified."
                return result
            except (OSError, ValueError) as exc:
                self._last_read = None
                return GestureResult(False, message=str(exc))
