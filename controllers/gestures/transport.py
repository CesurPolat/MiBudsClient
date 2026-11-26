"""Gesture operations using the shared RCSP config transaction channel."""
from utils.app.i18n import message as m, error_message
import time
from ..bluetooth.packets.config_transport import RcspConfigTransport
from .protocol import GestureResult, build_gesture_assignment, build_gesture_request, parse_gesture_records, gesture_config


class GestureTransport(RcspConfigTransport):
    @staticmethod
    def _parse(data):
        return parse_gesture_records(data, physical=True)

    def read(self, timeout=5.0, generation=None, configs=(2,)):
        if timeout <= 0:
            raise ValueError("Gesture timeout must be positive")
        generation = self.generation if generation is None else generation
        with self._serial:
            try:
                assignments = {}
                for config in configs:
                    data = self._exchange(0xF3, lambda ss: build_gesture_request(ss, config), timeout, generation, config_id=config)
                    assignments.update(self._parse(data))
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
                deadline = time.monotonic() + timeout
                revision = self.revision
                config = gesture_config(gesture_type)
                self._exchange(0xF2, lambda counter: build_gesture_assignment(
                    counter, gesture_type, side, action), timeout, generation, config_id=config)
                def read(remaining):
                    return self._parse(self._exchange(
                        0xF3, lambda ss: build_gesture_request(ss, config), remaining, generation, config_id=config))
                confirmed, assignments = self.confirm(
                    config, self._parse, read,
                    lambda values: gesture_type in values and values[gesture_type][0 if side in ("left", "common") else 1] == action,
                    max(0, deadline - time.monotonic()), generation, revision, namespace="gesture")
                self._last_read = assignments if confirmed else None
                if assignments is None:
                    return GestureResult(False, message=m("gesture.verification_failed", details=m("gesture.timeout")))
                return GestureResult(confirmed, assignments or {},
                                     m("gesture.saved" if confirmed else "gesture.unconfirmed"))
            except (OSError, ValueError) as exc:
                self._last_read = None
                return GestureResult(False, message=error_message(exc))
