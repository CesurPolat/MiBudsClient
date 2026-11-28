"""Schedule battery requests and use missing replies to assess link health."""

import time

from .stream import BATTERY_UNKNOWN, battery_state


class BatteryPolling:
    _REFRESH_INTERVAL = 60 * 5
    _RESPONSE_TIMEOUT = 10
    _MAX_ATTEMPTS = 3

    def __init__(self, *, lock, notify):
        self._lock = lock
        self._notify = notify
        self.enabled = False
        self._last_request_at = 0.0
        self._last_received_at = time.monotonic()
        self._next_check_at = 0.0
        self._has_value = False
        self._clear_pending()

    def _clear_pending(self):
        self._requested_at = None
        self._probe_started_at = None
        self._attempts = 0

    def set_active(self, active):
        """Refresh on foreground entry and coalesce quick focus changes."""
        with self._lock:
            active = bool(active)
            if active == self.enabled:
                return
            self.enabled = active
            if active:
                self._next_check_at = max(time.monotonic(), self._last_request_at + 5)
            else:
                self._clear_pending()

    def send_request(self, send, payload, *, user_initiated) -> bool:
        # Record before sending so a fast response cannot race this state.
        with self._lock:
            if not user_initiated and not self.enabled:
                return False
            now = time.monotonic()
            if self._requested_at is None:
                self._requested_at = self._probe_started_at = now
                self._attempts = 1
            send(payload)
            self._last_request_at = now
            return True

    def check_health(self, request):
        """Evaluate both idle socket timeouts and loops with incoming data."""
        invalidate = unresponsive = exhausted = False
        with self._lock:
            if not self.enabled:
                return
            now = time.monotonic()
            if self._requested_at is None:
                if now < self._next_check_at:
                    return
            elif now - self._requested_at < self._RESPONSE_TIMEOUT:
                return
            elif self._attempts < self._MAX_ATTEMPTS:
                self._attempts += 1
                self._requested_at = now
            else:
                # Missing battery data alone does not prove a dead transport.
                exhausted = True
                unresponsive = self._last_received_at <= self._probe_started_at
                invalidate = self._has_value
                self._has_value = False
                self._clear_pending()
                self._next_check_at = now + self._REFRESH_INTERVAL
        if invalidate:
            self._notify(BATTERY_UNKNOWN, BATTERY_UNKNOWN, BATTERY_UNKNOWN)
        if unresponsive:
            raise ConnectionError("No response to repeated battery health probes")
        if exhausted:
            return
        success, reason = request(user_initiated=False)
        if not success and self.enabled:
            raise ConnectionError(reason)

    def mark_received(self):
        with self._lock:
            self._last_received_at = time.monotonic()

    def on_statuses(self, statuses):
        with self._lock:
            self._clear_pending()
            self._has_value = True
            self._next_check_at = time.monotonic() + self._REFRESH_INTERVAL
        for status in statuses:
            values = []
            for label, raw in (("left", status.left), ("right", status.right), ("case", status.case)):
                state = battery_state(raw)
                value = "unknown"
                if state is not None:
                    percent, charging = state
                    value = f"{percent}%"
                    if charging:
                        value += " (charging)"
                values.append(f"{label}={value} [raw={raw}]")
            print("[Bluetooth] Battery received: " + "; ".join(values))
            self._notify(status.left, status.right, status.case)

    def reset(self):
        with self._lock:
            invalidate = self._has_value
            self._has_value = False
            self._clear_pending()
            self._next_check_at = 0.0
        if invalidate:
            self._notify(BATTERY_UNKNOWN, BATTERY_UNKNOWN, BATTERY_UNKNOWN)
