"""Track RCSP target information requests and the identity of the current peer."""

import threading
from dataclasses import dataclass

from utils.app.i18n import error_message, message as m
from utils.diagnostics.error_reports import redact

from .link.discovery import BluetoothDiscovery
from .packets.rcsp import DeviceIdentity, build_identity_request, is_supported_target, parse_identity_fields


@dataclass
class _IdentityRequest:
    counter: int
    completed: bool = False
    identity: DeviceIdentity | None = None
    error: str = ""
    raw_hex: str = ""


class IdentitySession:
    def __init__(self, on_identity):
        self._condition = threading.Condition()
        self._pending: _IdentityRequest | None = None
        self._counter = 0x90
        self._identity: DeviceIdentity | None = None
        self._last_identity = None
        self._on_identity = on_identity

    @property
    def current(self) -> DeviceIdentity | None:
        with self._condition:
            return self._identity

    def next_counter(self) -> int:
        # Identity and battery requests share the target-info sequence.
        with self._condition:
            counter = self._counter
            self._counter = (counter + 1) & 0xFF
            return counter

    def request(self, connection, timeout: float) -> tuple[bool, str]:
        with self._condition:
            if self._pending is not None:
                return False, m("identity.busy")
            request = _IdentityRequest(self.next_counter())
            self._pending = request

        try:
            connection.send(build_identity_request(request.counter))
            with self._condition:
                if not self._condition.wait_for(lambda: request.completed, timeout):
                    return False, m("identity.timeout")
                if request.error:
                    return False, request.error + (f"\nRX: {request.raw_hex}" if request.raw_hex else "")
                return True, f"{request.identity.describe()}\nRX: {request.raw_hex}"
        except Exception as exc:
            connection.connected = False
            return False, m("identity.failed", details=error_message(exc))
        finally:
            with self._condition:
                if self._pending is request:
                    self._pending = None

    def feed_packets(self, packets, *, address, device_name):
        identity = None
        with self._condition:
            for packet in packets:
                request = self._pending
                if request is None or request.completed:
                    continue
                if (packet.flags & 0x80 or not is_supported_target(packet.flags)
                        or packet.opcode != 0x02 or len(packet.payload) < 2):
                    continue
                status, counter = packet.payload[:2]
                if counter != request.counter:
                    continue
                request.raw_hex = packet.raw_hex
                if status != 0:
                    request.error = m("identity.rejected", code=f"{status:02X}")
                else:
                    request.identity = parse_identity_fields(packet.payload[2:])
                    if request.identity is None:
                        request.error = m("identity.invalid")
                    else:
                        identity = self._identity = request.identity
                        self._last_identity = (address, identity)
                request.completed = True
                self._condition.notify_all()
        if identity is not None:
            print(f"[Bluetooth] Device identity received: {redact(self.diagnostics(address, device_name))}")
            if self._on_identity:
                self._on_identity(identity)

    def diagnostics(self, address, device_name) -> dict:
        """Use only identity read from this peer, including its last session."""
        with self._condition:
            identity = self._identity
            source = "current_session"
            if identity is None and self._last_identity is not None:
                previous_address, previous = self._last_identity
                if BluetoothDiscovery._format_mac(previous_address) == BluetoothDiscovery._format_mac(address):
                    identity, source = previous, "previous_session"
            if identity is None:
                return {"status": "unavailable", "device_name": device_name}
            return {
                "status": "available", "source": source, "device_name": device_name,
                "vid": f"0x{identity.vid:04X}", "pid": f"0x{identity.pid:04X}",
                "firmware_version": identity.firmware_version,
                "model_name": identity.model_name, "model_codes": list(identity.model_codes),
            }

    def reset(self, reason):
        with self._condition:
            self._identity = None
            request = self._pending
            if request is not None and not request.completed:
                request.error = reason
                request.completed = True
                self._condition.notify_all()
