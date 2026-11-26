"""Write once, then await device confirmation within one time budget."""
import math
import threading
import time
from dataclasses import replace

from utils.app.i18n import message as m
from .protocol import build_noise_mode, build_noise_level, build_noise_read, parse_noise_state, wear_requirement
from ..bluetooth.packets.config_transport import parse_config_records
from ..bluetooth.packets.rcsp import build_command_frame


class NoiseTransport:
    def __init__(self, channel):
        self.channel = channel
        self._updates = threading.Condition()
        self._revision = 0
        self._notification = None
        self._aux_session = None
        self._wear = self._adaptive = None
        self._last_state = None

    def reset(self):
        """Called after the shared channel generation changes on disconnect."""
        with self._updates:
            self._notification = None
            self._aux_session = None
            self._wear = self._adaptive = None
            self._last_state = None
            self._revision += 1
            self._updates.notify_all()

    def notify(self, session, state):
        """Receive parsed F4 state from the existing socket listener."""
        with self._updates:
            if session != self.channel.generation:
                return
            self._notification = (session, self.enrich(session, state))
            self._last_state = self._notification[1]
            self._revision += 1
            self._updates.notify_all()

    def enrich(self, session, state):
        return replace(state, wear=self._wear, adaptive=self._adaptive) if self._aux_session == session else state

    def current_state(self, session):
        if self._last_state is not None and self._aux_session == session:
            return self.enrich(session, self._last_state)
        return None

    def notify_aux(self, session, records):
        with self._updates:
            if session != self.channel.generation:
                return
            self._aux_session = session
            if 12 in records and len(records[12]) == 1:
                self._wear = records[12][0]
            if records.get(37) in (b"\x00", b"\x01"):
                self._adaptive = records[37] == b"\x01"
            if self._notification is not None and self._notification[0] == session:
                self._notification = (session, self.enrich(session, self._notification[1]))
            self._revision += 1
            self._updates.notify_all()

    def read_aux(self, capabilities, session, timeout=0.4):
        for config in (12, 37) if capabilities.adaptive == "switch" else (12,):
            try:
                data = self.channel.exchange(0xF3, lambda ss: build_command_frame(0xF3, ss, config.to_bytes(2, "big")),
                                             timeout, session, config, namespace="noise")
                self.notify_aux(session, parse_config_records(data))
            except (OSError, ValueError):
                self._check_session(session)

    def set_adaptive(self, capabilities, session, enabled, timeout=2.0):
        if capabilities.adaptive != "switch" or type(enabled) is not bool:
            raise ValueError("Separate adaptive noise control is unavailable")
        with self.channel.transaction():
            revision = self.channel.revision
            deadline = time.monotonic() + timeout
            self.channel.exchange(0xF2, lambda ss: build_command_frame(0xF2, ss, bytes((3, 0, 37, int(enabled)))),
                                  timeout, session, 37, namespace="noise")
            def parse(data):
                value = parse_config_records(data).get(37)
                if value not in (b"\x00", b"\x01"):
                    raise ValueError("Invalid adaptive noise state")
                return value == b"\x01"
            confirmed, actual = self.channel.confirm(
                37, parse,
                lambda remaining: parse(self.channel.exchange(0xF3, lambda ss: build_command_frame(0xF3, ss, b"\x00\x25"),
                                       remaining, session, 37, namespace="noise")),
                lambda value: value == enabled, max(0, deadline - time.monotonic()), session, revision, namespace="noise")
            self._aux_session, self._adaptive = session, actual
            if not confirmed:
                raise TimeoutError(m("noise.unconfirmed"))
            return self.read(session, max(0.1, deadline - time.monotonic()))

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
        state = self.enrich(session, parse_noise_state(self.channel.exchange(
            0xF3, build_noise_read, timeout, session, 11, namespace="noise")))
        self._check_session(session)
        self._last_state = state
        return state

    def apply(self, capabilities, session, mode, level=None, timeout=2.0):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Noise timeout must be finite and positive")
        if type(mode) is not int or mode not in capabilities.modes:
            raise ValueError("Unsupported noise mode")
        reason = wear_requirement(capabilities, self._wear if self._aux_session == session else None, mode)
        if reason:
            raise ValueError(m(reason))
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
