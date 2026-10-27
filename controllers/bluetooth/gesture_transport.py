"""Gesture operations using the shared RCSP config transaction channel."""
from utils.i18n import message as m, error_message
from .config_transport import RcspConfigTransport
from .gestures import GestureResult, build_gesture_assignment, build_gesture_request, parse_gesture_records


class GestureTransport(RcspConfigTransport):
    def read(self, timeout=5.0, generation=None):
        if timeout <= 0:
            raise ValueError("Gesture timeout must be positive")
        generation = self.generation if generation is None else generation
        with self._serial:
            try:
                data = self._exchange(0xF3, build_gesture_request, timeout, generation, config_id=2)
                assignments = parse_gesture_records(data)
                with self._condition:
                    if generation != self._generation:
                        raise ConnectionError(m("gesture.connection_changed"))
                    self._last_read = dict(assignments)
                return GestureResult(True, assignments, m("gesture.loaded"))
            except (OSError, ValueError) as exc:
                self._last_read = None
                return GestureResult(False, message=error_message(exc))

    def write(self, gesture_type, side, action, timeout=5.0, generation=None):
        if timeout <= 0:
            raise ValueError("Gesture timeout must be positive")
        generation = self.generation if generation is None else generation
        with self._serial:
            try:
                with self._condition:
                    if self._last_read is None or gesture_type not in self._last_read:
                        raise ValueError(m("gesture.refresh_first"))
                    self._last_read = None
                self._exchange(0xF2, lambda counter: build_gesture_assignment(
                    counter, gesture_type, side, action), timeout, generation, config_id=2)
                result = self.read(timeout, generation)
                if not result.success:
                    return GestureResult(False, message=m("gesture.verification_failed", details=result.message))
                actual = result.assignments.get(gesture_type)
                if actual is None or actual[0 if side == "left" else 1] != action:
                    self._last_read = None
                    return GestureResult(False, message=m("gesture.unconfirmed"))
                result.message = m("gesture.saved")
                return result
            except (OSError, ValueError) as exc:
                self._last_read = None
                return GestureResult(False, message=error_message(exc))
