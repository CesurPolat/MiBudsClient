"""Bounded mutual 50/51 authentication; never owns a socket reader.

Strict validation and total deadline are Python policy, not claims about APK
behavior. The alternative raw SPP session lives in raw_auth.py.
"""
import hmac
import secrets
import time
import threading
from functools import wraps
from enum import Enum

from .auth_codec import decode_auth, encode_auth
from ..packets.rcsp import RcspStreamParser
from .safer_plus import challenge_response


class AuthPolicy(str, Enum):
    AUTO = "auto"
    DIRECT = "direct"
    COMMAND = "command_auth"
    UNKNOWN = "unknown"
    RAW = "raw_auth"


def profile_auth_policy(name):
    # Kept for callers of the older API; service selection happens after SDP.
    return AuthPolicy.AUTO


class AuthError(ConnectionError):
    pass


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


class CommandAuthSession:
    def __init__(self, send, *, clock=time.monotonic, random_bytes=None,
                 next_sequence=None, timeout=25.0, trace=None):
        if timeout <= 0:
            raise ValueError("Auth timeout must be positive")
        self._send = send
        self._trace_callback = trace
        self._lock = threading.RLock()
        self._clock = clock
        self._random = random_bytes if random_bytes is not None else secrets.token_bytes
        self._next_sequence = next_sequence
        self._counter = 0
        self._timeout = timeout
        self._parser = RcspStreamParser()
        self.state = "idle"
        self._pending = {}
        self._expected = None
        self._deadline = None
        self.error = ""
        self._last_rx = None
        self._replies = {}
        self.failure_diagnostics = None
        self._last_decision = None

    def _trace(self, event, **details):
        """Only framing metadata; never challenges or cipher answers."""
        self._last_decision = {"event": event, "state": self.state, **details}
        if self._trace_callback is not None:
            self._trace_callback("authentication", event=event, state=self.state, **details)

    @_serialized
    def diagnostics(self):
        now = self._clock()
        return {"state_before_failure": self.state,
                "elapsed": None if self._deadline is None else round(now - self._deadline + self._timeout, 3),
                "remaining": None if self._deadline is None else round(max(0, self._deadline - now), 3),
                "pending": [{"opcode": f"0x{op:02X}", "sequence": seq, "retry": value[3]}
                            for (op, seq), value in self._pending.items()],
                "last_rx": self._last_rx, "last_decision": self._last_decision,
                "buffered_bytes": self._parser.buffered_bytes}

    @property
    def authenticated(self):
        return self.state == "authenticated"

    def _sequence(self):
        if self._next_sequence is not None:
            return self._next_sequence()
        result = self._counter
        self._counter = (result + 1) & 255
        return result

    @_serialized
    def reset(self):
        self.state = "idle"
        self.error = ""
        self._pending.clear()
        self._expected = None
        self._deadline = None
        self._parser.reset()
        self._last_rx = None
        self._replies.clear()
        self.failure_diagnostics = None
        self._last_decision = None

    @_serialized
    def abort(self, reason="Auth cancelled"):
        self.reset()
        self.state = "failed"
        self.error = reason

    def _fail(self, reason):
        snapshot = self.diagnostics()
        self._trace("failure", reason=reason)
        self.abort(reason)
        self.failure_diagnostics = snapshot
        raise AuthError(reason)

    def _request(self, opcode, payload, timeout):
        sequence = self._sequence()
        frame = encode_auth(opcode, sequence, payload)
        self._pending[(opcode, sequence)] = [frame, timeout, self._clock() + timeout, 0]
        self._trace("tx_request", opcode=f"0x{opcode:02X}", sequence=sequence,
                    length=1 + len(payload))
        self._send(frame)

    @_serialized
    def start(self):
        if self.state != "idle":
            raise AuthError("Auth session already started; reset before reconnect")
        challenge = self._random(16)
        self._expected = challenge_response(challenge)
        self._deadline = self._clock() + self._timeout
        self.state = "waiting_answer"
        self._request(0x50, bytes.fromhex("01") + challenge, 2.0)

    @_serialized
    def tick(self):
        if self.state in ("idle", "failed", "authenticated"):
            return
        now = self._clock()
        if now >= self._deadline:
            self._fail("Auth session timed out")
        for pending in self._pending.values():
            if now >= pending[2]:
                if pending[3] >= 3:
                    self._fail("Auth response timed out")
                pending[3] += 1
                pending[2] = now + pending[1]
                self._trace("retry", opcode=f"0x{pending[0][4]:02X}",
                            sequence=pending[0][7], attempt=pending[3])
                self._send(pending[0])

    @_serialized
    def feed(self, data):
        """Consume auth frames and return complete normal frames after success."""
        self.tick()
        normal = []
        try:
            for packet in self._parser.feed(data):
                if packet.opcode in (0x50, 0x51) and not self.authenticated:
                    sequence_index = 0 if packet.flags & 0x80 else 1
                    self._last_rx = {"flags": f"0x{packet.flags:02X}", "opcode": f"0x{packet.opcode:02X}",
                                     "length": len(packet.payload),
                                     "sequence": packet.payload[sequence_index] if len(packet.payload) > sequence_index else None,
                                     "status": packet.payload[0] if sequence_index == 1 and packet.payload else None}
                    self._trace("rx", flags=f"0x{packet.flags:02X}",
                                opcode=f"0x{packet.opcode:02X}",
                                sequence=(packet.payload[sequence_index]
                                          if len(packet.payload) > sequence_index else None),
                                length=len(packet.payload))
                frame = decode_auth(packet)
                if packet.opcode in (0x50, 0x51) and self._last_rx is not None:
                    self._last_rx["decision"] = "accepted_role" if frame is not None else "ignored_role"
                if frame is not None and frame.request:
                    cached = self._replies.get((frame.opcode, frame.sequence))
                    if cached is not None:
                        if frame.data != cached[0]:
                            self._fail("Auth request reused sequence with different data")
                        if cached[2] < 3:
                            cached[2] += 1
                            self._send(cached[1])
                            self._trace("replayed_response", opcode=f"0x{frame.opcode:02X}", sequence=frame.sequence)
                        continue
                if self.authenticated:
                    if packet.opcode not in (0x50, 0x51):
                        normal.append(bytes.fromhex(packet.raw_hex))
                    continue
                if self.state in ("idle", "failed"):
                    raise AuthError("Auth session is not active")
                if frame is None:
                    if packet.opcode in (0x50, 0x51):
                        self._trace("ignored_flags", flags=f"0x{packet.flags:02X}")
                    continue  # Normal commands are not replayed from before READY.
                if not frame.request:
                    key = (frame.opcode, frame.sequence)
                    if key not in self._pending:
                        self._trace("ignored_response", opcode=f"0x{frame.opcode:02X}",
                                    sequence=frame.sequence)
                        continue
                    if frame.status:
                        self._fail("Auth response returned nonzero status")
                    del self._pending[key]
                    if frame.opcode == 0x51:
                        if frame.data != bytes.fromhex("01"):
                            self._fail("Invalid auth result ACK")
                        continue  # Our ACK never authenticates the peer.
                    if self.state != "waiting_answer":
                        self._fail("Unexpected challenge response stage")
                    if len(frame.data) != 17 or frame.data[0] != 1:
                        self._fail("Invalid auth answer length/version")
                    if not hmac.compare_digest(frame.data[1:], self._expected):
                        self._send(encode_auth(0x51, self._sequence(), bytes.fromhex("01 01")))
                        self._fail("Auth challenge answer mismatch")
                    self._expected = None
                    self.state = "waiting_challenge"
                    self._request(0x51, bytes.fromhex("01 00"), 12.0)
                elif frame.opcode == 0x50:
                    if self.state != "waiting_challenge":
                        self._fail("Peer challenge arrived out of order")
                    if len(frame.data) != 17 or frame.data[0] != 1:
                        self._fail("Invalid peer challenge length/version")
                    answer = challenge_response(frame.data[1:])
                    self.state = "waiting_result"
                    self._trace("tx_response", opcode="0x50", sequence=frame.sequence,
                                length=19)
                    reply = encode_auth(0x50, frame.sequence, bytes.fromhex("01") + answer, request=False)
                    self._replies[(0x50, frame.sequence)] = [frame.data, reply, 0]
                    self._send(reply)
                else:
                    if self.state != "waiting_result" or len(frame.data) != 2 or frame.data[0] != 1:
                        self._fail("Invalid peer auth result/stage")
                    reply = encode_auth(0x51, frame.sequence, bytes.fromhex("01"), request=False)
                    self._replies[(0x51, frame.sequence)] = [frame.data, reply, 0]
                    self._send(reply)
                    if frame.data[1]:
                        self._fail("Peer rejected authentication")
                    self.state = "authenticated"
                    self._trace("complete")
                    self._pending.clear()
                    self._expected = None
        except ValueError as exc:
            self._fail(str(exc))
        if self.authenticated:
            tail = self._parser.take_buffer()
            if tail:
                normal.append(tail)
        return normal
