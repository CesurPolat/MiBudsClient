"""Write once, then await device confirmation within one time budget."""
import math
import threading
import time

from utils.i18n import message as m
from .noise import build_noise_mode, build_noise_level, build_noise_read, parse_noise_state


class NoiseTransport:
    def __init__(self, channel):
        self.channel = channel
        self._updates = threading.Condition()
        self._revision = 0
        self._notification = None

    def reset(self):
        """Called after the shared channel generation changes on disconnect."""
        with self._updates:
            self._notification = None
            self._revision += 1
            self._updates.notify_all()

    def notify(self, session, state):
        """Receive parsed F4 state from the existing socket listener."""
        with self._updates:
            if session != self.channel.generation:
                return
            self._notification = (session, state)
            self._revision += 1
            self._updates.notify_all()

    def _check_session(self, session):
        if session != self.channel.generation:
            raise ConnectionError(m("noise.connection_changed"))

    @staticmethod
    def _matches(state, mode, level):
        return state.mode == mode and (level is None or state.level == level)

    def _wait_for_confirmation(self, session, mode, level, deadline, revision):
        # Application pacing values, not measured firmware timing guarantees.
        read_interval = 0.2
        response_window = 0.4
        next_read = time.monotonic()
        while True:
            with self._updates:
                self._check_session(session)
                now = time.monotonic()
                remaining = deadline - now
                if remaining <= 0:
                    raise TimeoutError("Device readback could not confirm the requested noise setting before timeout")
                if self._revision != revision:
                    revision = self._revision
                    notification = self._notification
                    if notification is not None and notification[0] == session:
                        actual = notification[1]
                        if self._matches(actual, mode, level):
                            return actual

                if now < next_read:
                    self._updates.wait(min(next_read - now, remaining))
                    continue

            next_read = time.monotonic() + read_interval
            read_timeout = min(response_window, deadline - time.monotonic())
            if read_timeout <= 0:
                continue
            try:
                actual = self.read(session, read_timeout)
            except TimeoutError:
                # A missing response is retryable within the shared deadline.
                # Rejections, disconnects and malformed responses still fail.
                continue
            self._check_session(session)
            if time.monotonic() <= deadline and self._matches(actual, mode, level):
                return actual

    def read(self, session, timeout=2.0):
        return parse_noise_state(self.channel.exchange(
            0xF3, build_noise_read, timeout, session, 11, namespace="noise"))

    def apply(self, capabilities, session, mode, level=None, timeout=2.0):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Noise timeout must be finite and positive")
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
            self._check_session(session)
            deadline = time.monotonic() + timeout
            with self._updates:
                # Ignore any notification cached before this write began.
                revision = self._revision
            # ACK rawData is not CommonConfig and is never reported as state.
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(m("noise.timeout"))
            self.channel.exchange(opcode, builder, remaining,
                                  session, None, namespace="noise")
            return self._wait_for_confirmation(session, mode, level, deadline, revision)
