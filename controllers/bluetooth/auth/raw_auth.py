"""Mutual raw SPP authentication, with a bounded receive buffer and deadline.

Wire messages: 00 + challenge[16], 01 + answer[16], 02 + ASCII 'pass'.
The existing cipher matches the inspected ARM64 JNI implementation; see
docs/raw-auth.md for artifact identity and the limits of that evidence.
"""
import hmac
import secrets
import threading
import time

from .auth_session import AuthError, _serialized
from .safer_plus import challenge_response


AUTH_PASS = bytes.fromhex("02 70 61 73 73")


def raw_auth_response(message: bytes) -> bytes:
    if len(message) != 17 or message[0] != 0:
        raise ValueError("Expected raw auth challenge: 00 + 16 bytes")
    return bytes.fromhex("01") + challenge_response(message[1:])


class RawAuthSession:
    """Single-reader session; feed returns bytes only after mutual success.

    Retry the initial unanswered challenge at 0.5, 3.5 and 6.5 seconds.
    The whole exchange expires at 9.5 seconds. Unlike the APK's timer, do not
    restart the challenge after the peer has answered it.
    """

    def __init__(self, send, *, clock=time.monotonic, random_bytes=None,
                 timeout=9.5):
        if timeout <= 0:
            raise ValueError("Auth timeout must be positive")
        self._send = send
        self._clock = clock
        self._random = random_bytes if random_bytes is not None else secrets.token_bytes
        self._timeout = timeout
        self._lock = threading.RLock()
        self.reset()

    @property
    def authenticated(self):
        return self.state == "authenticated"

    @_serialized
    def reset(self):
        self.state = "idle"
        self.error = ""
        self._buffer = bytearray()
        self._challenge = None
        self._expected = None
        self._deadline = None
        self._next_send = None
        self._attempts = 0
        self.failure_diagnostics = None
        self._peer_challenge = self._peer_answer = self._own_answer = None
        self._replays = 0
        self._last_rx = None

    @_serialized
    def diagnostics(self):
        now = self._clock()
        return {"state_before_failure": self.state,
                "elapsed": None if self._deadline is None else round(now - self._deadline + self._timeout, 3),
                "remaining": None if self._deadline is None else round(max(0, self._deadline - now), 3),
                "retry": self._attempts, "buffered_bytes": len(self._buffer), "last_rx": self._last_rx}

    @_serialized
    def abort(self, reason="Auth cancelled"):
        self.reset()
        self.state = "failed"
        self.error = reason

    def _fail(self, reason):
        snapshot = self.diagnostics()
        self.abort(reason)
        self.failure_diagnostics = snapshot
        raise AuthError(reason)

    def _write(self, message):
        try:
            self._send(message)
        except Exception as exc:
            self.abort("Raw auth send failed")
            raise AuthError(self.error) from exc

    @_serialized
    def start(self):
        if self.state != "idle":
            raise AuthError("Auth session already started; reset before reconnect")
        challenge = self._random(16)
        if len(challenge) != 16:
            self._fail("Invalid raw auth random challenge length")
        self._challenge = bytes.fromhex("00") + challenge
        self._expected = raw_auth_response(self._challenge)
        now = self._clock()
        self._deadline = now + self._timeout
        self._next_send = now + 0.5
        self.state = "waiting_answer"

    @_serialized
    def tick(self):
        if self.state in ("idle", "failed", "authenticated"):
            return
        now = self._clock()
        if now >= self._deadline:
            self._fail("Raw auth session timed out")
        if (self.state == "waiting_answer" and self._attempts < 3
                and now >= self._next_send):
            self._attempts += 1
            self._next_send = now + 3.0
            self._write(self._challenge)

    @_serialized
    def feed(self, data):
        self.tick()
        if self.authenticated:
            return [bytes(data)] if data else []
        if self.state in ("idle", "failed"):
            raise AuthError("Raw auth session is not active")
        self._buffer.extend(data)
        while self._buffer:
            kind = self._buffer[0]
            self._last_rx = {"type": kind, "buffered_bytes": len(self._buffer)}
            # Only exact repeats of an already verified message are idempotent.
            # Different data and new out-of-order requests still fail below.
            cached = ((self._own_answer, AUTH_PASS) if kind == 1 else
                      (self._peer_challenge, self._peer_answer) if kind == 0 else (None, None))
            if cached[0] is not None:
                if len(self._buffer) < 17:
                    break
                if bytes(self._buffer[:17]) != cached[0]:
                    self._fail("Raw auth retry data mismatch")
                del self._buffer[:17]
                if self._replays < 3:
                    self._replays += 1
                    self._write(cached[1])
                continue
            expected_type = {"waiting_answer": 1, "waiting_challenge": 0,
                             "waiting_result": 2}[self.state]
            if self._buffer[0] != expected_type:
                self._fail("Unexpected raw auth message or stage")
            size = 5 if expected_type == 2 else 17
            if expected_type == 2 and not AUTH_PASS.startswith(bytes(self._buffer[:size])):
                self._fail("Peer rejected raw authentication or sent an invalid result")
            if len(self._buffer) < size:
                break
            message = bytes(self._buffer[:size])
            del self._buffer[:size]
            if self.state == "waiting_answer":
                if not hmac.compare_digest(message, self._expected):
                    self._fail("Raw auth challenge answer mismatch")
                self._own_answer = message
                self._challenge = self._expected = None
                self._next_send = None
                self.state = "waiting_challenge"
                self._write(AUTH_PASS)
            elif self.state == "waiting_challenge":
                answer = raw_auth_response(message)
                self._peer_challenge, self._peer_answer = message, answer
                self.state = "waiting_result"
                self._write(answer)
            else:
                self.state = "authenticated"
                self._deadline = self._next_send = None
                self._challenge = self._expected = None
                tail = bytes(self._buffer)
                self._buffer.clear()
                return [tail] if tail else []
        return []
