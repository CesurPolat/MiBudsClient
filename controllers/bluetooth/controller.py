"""Main Bluetooth Controller for Mi Buds."""

from utils.i18n import message as m, error_message

import socket
import errno
import threading
import time
import traceback
from utils.error_reports import redact
from utils.user_preferences import get_selected_bluetooth_address, set_selected_bluetooth_address
from dataclasses import dataclass
from functools import partial
from typing import Callable, Optional

from ..battery.stream import BatteryStreamParser
from ..catalog.capabilities import resolve_capabilities, DeviceCapabilities
from ..catalog.device_catalog import catalog_diagnostics
from ..equalizer.protocol import EqResult, eq_profiles
from ..equalizer.transport import EqTransport
from ..gestures.protocol import GestureResult, gesture_capabilities, gesture_config, parse_gesture_records
from ..gestures.transport import GestureTransport
from ..latency.transport import LatencyTransport
from ..noise.capture import record
from ..noise.protocol import noise_capabilities, noise_backend_enabled, parse_noise_notification
from ..noise.transport import NoiseTransport
from .link.connection import BluetoothConnection
from .auth.auth_session import AuthPolicy, AuthError, CommandAuthSession
from .link.sdp import ConnectionCancelled
from .link.discovery import BluetoothDiscovery
from .packets.protocol import BudsProtocol
from .packets.config_transport import parse_config_records
from .packets.rcsp import DeviceIdentity, RcspStreamParser, build_identity_request, is_supported_target, parse_identity_fields


RECONNECT_DELAY = 5


@dataclass
class _IdentityRequest:
    counter: int
    completed: bool = False
    identity: Optional[DeviceIdentity] = None
    error: str = ""
    raw_hex: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Type Aliases
# ─────────────────────────────────────────────────────────────────────────────
StatusCallback = Callable[[str, str], None]
BatteryCallback = Callable[[int, int, int], None]
CheckBatteryCallback = Callable[[], None]
ConnectionEventCallback = Callable[[str], None]


# ─────────────────────────────────────────────────────────────────────────────
# Controller
# ─────────────────────────────────────────────────────────────────────────────
class BTController:
    """High-level controller for Mi Buds communication."""

    _STALE_CONNECTION_TIMEOUT = 12
    _BATTERY_REFRESH_INTERVAL = 60 * 5
    _BATTERY_RESPONSE_TIMEOUT = 10
    _BATTERY_MAX_ATTEMPTS = 3
    _RECONNECT_COOLDOWN = 120
    
    def __init__(
        self,
        status_callback: Optional[StatusCallback] = None,
        battery_callback: Optional[BatteryCallback] = None,
        check_battery_callback: Optional[CheckBatteryCallback] = None,
        connection_event_callback: Optional[ConnectionEventCallback] = None,
        bd_addr: Optional[str] = None,
        identity_callback: Optional[Callable[[DeviceIdentity], None]] = None,
        connection_state_callback: Optional[Callable[[str, str], None]] = None,
        auth_policy: AuthPolicy | str | None = None,
        error_callback: Optional[Callable] = None,
    ):
        self._connection = BluetoothConnection(on_send=partial(record, "TX"))
        self._auth_policy = AuthPolicy(auth_policy) if auth_policy is not None else None
        self._protocol = BudsProtocol()
        self._battery_parser = BatteryStreamParser()
        self._gestures = GestureTransport(self._connection)
        self._equalizer = EqTransport(self._gestures)
        self._latency = LatencyTransport(self._gestures)
        self._noise = NoiseTransport(self._gestures)
        self._noise_parser = RcspStreamParser()
        self._rx_lock = threading.RLock()
        self.config_callback = None
        self.device_candidates_callback = None
        self._device_candidates = ()
        self.noise_callback = None
        self._bd_addr = bd_addr
        self._device_name = ""
        self._error_callback = error_callback
        self._device_check = {"state": "unknown"}
        self._discovery_devices = []
        self._running = True
        self._connect_lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._identity_condition = threading.Condition()
        self._identity_parser = RcspStreamParser()
        self._identity_pending: Optional[_IdentityRequest] = None
        self._identity_counter = 0x90
        self._identity: Optional[DeviceIdentity] = None
        self._last_identity = None
        self._identity_callback = identity_callback
        self._max_reconnect_attempts = 5
        self._reconnect_attempts = 0
        self._reconnect_paused = False
        self._reconnect_retry_at = 0.0
        self._battery_requested_at = None
        self._battery_probe_started_at = None
        self._battery_attempts = 0
        self._battery_next_check_at = 0.0
        self._battery_has_value = False
        self._battery_polling_enabled = False
        self._battery_last_request_at = 0.0
        self._last_received_at = time.monotonic()
        self._last_connection_event: Optional[str] = None
        self._last_connection_failure = ""
        
        # Callbacks
        self._status_callback = status_callback
        self._battery_callback = battery_callback
        self._check_battery_callback = check_battery_callback
        self._connection_event_callback = connection_event_callback
        self._connection_state_callback = connection_state_callback

    def _notify_connection_state(self, state: str, reason: str = "") -> None:
        if state != "retrying":  # Do not repeat the countdown every second.
            print(redact(f"[Bluetooth] state={state} reason={reason}"))
        if state == "failed" and reason:
            self._last_connection_failure = reason
        elif state == "connected":
            self._last_connection_failure = ""
        if self._connection_state_callback:
            self._connection_state_callback(state, reason)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────────────────
    @property
    def connected(self) -> bool:
        """Check if connected to device."""
        return self._connection.connected

    @property
    def connection_result(self):
        """Transport metadata for session/auth selection; not proof of auth."""
        return self._connection.result

    @property
    def session_ready(self):
        return self.connected and self._connection.session_ready

    @property
    def transport_connected(self):
        return self._connection.transport_connected

    @property
    def session_authenticated(self):
        return self.connected and self._connection.session_authenticated

    @property
    def device_name(self) -> str:
        return self._device_name if self.connected else ""

    @property
    def device_identity(self) -> Optional[DeviceIdentity]:
        with self._identity_condition:
            return self._identity

    @property
    def diagnostic_identity(self) -> dict:
        """Use only identity read from this peer, including its last session."""
        with self._identity_condition:
            identity = self._identity
            source = "current_session"
            if identity is None and self._last_identity is not None:
                address, previous = self._last_identity
                if BluetoothDiscovery._format_mac(address) == BluetoothDiscovery._format_mac(self._bd_addr):
                    identity, source = previous, "previous_session"
            if identity is None:
                return {"status": "unavailable", "device_name": self._device_name}
            return {
                "status": "available", "source": source,
                "device_name": self._device_name,
                "vid": f"0x{identity.vid:04X}", "pid": f"0x{identity.pid:04X}",
                "firmware_version": identity.firmware_version,
                "model_name": identity.model_name, "model_codes": list(identity.model_codes),
            }
    
    # ─────────────────────────────────────────────────────────────────────────
    # Status Updates
    # ─────────────────────────────────────────────────────────────────────────
    def _update_status(self, text: str, color: str = "black") -> None:
        """Send status update to UI."""
        if self._status_callback:
            self._status_callback(text, color)
    
    def _trigger_battery_check(self) -> None:
        """Trigger battery check callback."""
        if self._check_battery_callback:
            self._check_battery_callback()
    
    def _notify_battery(self, left: int, right: int, case: int) -> None:
        """Notify UI of battery status."""
        if self._battery_callback:
            self._battery_callback(left, right, case)

    def _notify_connection_event(self, event: str) -> None:
        """Notify UI about connection event transitions."""
        if event == self._last_connection_event:
            return

        self._last_connection_event = event
        if self._connection_event_callback:
            self._connection_event_callback(event)

    def _reset_reconnect_state(self) -> None:
        with self._state_lock:
            self._reconnect_attempts = 0
            self._reconnect_paused = False
            self._reconnect_retry_at = 0.0

    def _record_reconnect_failure(self) -> tuple[int, bool]:
        with self._state_lock:
            self._reconnect_attempts += 1
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                self._reconnect_paused = True
                self._reconnect_retry_at = time.monotonic() + self._RECONNECT_COOLDOWN
            return self._reconnect_attempts, self._reconnect_paused

    def resume_reconnect_attempts(self) -> None:
        """Allow reconnect attempts again after user interaction."""
        self._reset_reconnect_state()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Connection
    # ─────────────────────────────────────────────────────────────────────────
    def connect(self) -> bool:
        """Connect to the Mi Buds device."""
        with self._connect_lock:
            if not self._running:
                return False
            if self._connection.connected:
                return True

            self._notify_connection_state("connecting")
            self._connection.diagnostics = []
            self._connection.stage = "discovery"
            self._device_check = {"state": "unknown"}
            self._discovery_devices = []
            try:
                if not self._bd_addr:
                    preferred = get_selected_bluetooth_address()
                    devices = BluetoothDiscovery.get_connected_devices(preferred)
                    self._device_candidates = devices
                    if self.device_candidates_callback:
                        self.device_candidates_callback(devices)
                    device = next((item for item in devices if item.address == preferred), None)
                    if device is None and len(devices) == 1:
                        device = devices[0]
                    self._discovery_devices = BluetoothDiscovery.discovery_diagnostics()
                    if not device or not device.address:
                        reason = m("connection.choose_device" if devices else "connection.no_catalog")
                        self._notify_connection_state("failed", reason)
                        self._update_status(reason if devices else m("connection.no_device"), "red")
                        if not devices:
                            self._report_connection_error(ConnectionError(str(reason)), "bluetooth_discovery")
                        return False
                    self._bd_addr = device.address
                    self._device_name = device.name
                    set_selected_bluetooth_address(device.address)
                self._device_check = BluetoothDiscovery.connection_state(self._bd_addr)
                print(f"[Bluetooth] Device check: {redact(self._device_check)}")
                self._reset_identity_state(m("identity.connection_changed"))
                policy = self._auth_policy or AuthPolicy.AUTO
                connected_caps = resolve_capabilities(self._device_name)
                self._connection.connect(self._bd_addr, device_name=self._device_name, session_policy=policy)
                if not self._running:
                    self._connection.disconnect()
                    return False
                if noise_backend_enabled(connected_caps):
                    result = self._connection.result
                    record("SESSION", model=connected_caps.model, device_name=self._device_name,
                           service_uuid=result.service_uuid, channel=result.channel,
                           resolution_source=result.resolution_source,
                           auth_policy=policy.value, authenticated=self.session_authenticated)
                self._update_status(m("connection.connected"), "blue")
                with self._state_lock:
                    self._last_received_at = time.monotonic()
                self._reset_reconnect_state()
                self._notify_connection_state("connected")
                self._notify_connection_event("connected")
                self.on_connect_setup()
                return True
            except Exception as e:
                if not self._running or isinstance(e, ConnectionCancelled):
                    return False
                self._connection.connected = False
                self._update_status(m("connection.failure_details", details=str(e)), "red")
                reason = self._connection_failure_reason(e)
                self._notify_connection_state("failed", m("connection.technical", reason=reason, details=str(e) or type(e).__name__))
                self._report_connection_error(e, "bluetooth_connect")
                return False

    def _connection_failure_reason(self, error):
        """Classify wrapped SDP/socket errors using their original causes."""
        causes, visited = [], set()
        while error is not None and id(error) not in visited and len(causes) < 8:
            visited.add(id(error))
            causes.append(error)
            error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
        if any(isinstance(cause, AuthError) for cause in causes):
            return m("connection.auth_failed")
        if self._device_check.get("state") == "disconnected":
            return m("connection.disconnected_reason")
        if any(isinstance(cause, PermissionError)
               or getattr(cause, "errno", None) in (errno.EACCES, errno.EPERM, 10013)
               or getattr(cause, "winerror", None) in (5, 10013) for cause in causes):
            return m("connection.permission")
        if any(isinstance(cause, (TimeoutError, socket.timeout))
               or getattr(cause, "errno", None) in (errno.ETIMEDOUT, 10060)
               or getattr(cause, "winerror", None) == 10060 for cause in causes):
            return m("connection.timeout")
        return m("connection.service_failed" if self._connection.stage == "resolution"
                 else "connection.establish_failed")

    def _report_connection_error(self, error, action):
        """Forward handled transport failures to automatic reporting."""
        from .debug.diagnostics import implementation_diagnostics
        error.bluetooth_diagnostics = {
            "device": self._device_name,
            "device_check": self._device_check,
            "discovered_devices": self._discovery_devices,
            "stage": "receive" if action == "bluetooth_receive" else self._connection.stage,
            "transport": list(self._connection.diagnostics),
            "authentication": self._connection.auth_diagnostics,
            "identity": self.diagnostic_identity,
            "catalog": catalog_diagnostics(),
            "implementation": implementation_diagnostics(),
            "catalog_match": {"model": resolve_capabilities(self._device_name).model,
                              "source": "bluetooth_name", "device_identity_verified": False},
        }
        print(f"[Bluetooth] Error report device identity: {redact(error.bluetooth_diagnostics['identity'])}")
        print(redact("".join(traceback.format_exception(type(error), error, error.__traceback__))))
        if self._error_callback:
            try:
                self._error_callback(error, action)
            except Exception as exc:
                print(f"[Bluetooth] Could not prepare error report: {redact(exc)}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Commands
    # ─────────────────────────────────────────────────────────────────────────
    def send_command(self, mode: str = "low") -> tuple[bool, str]:
        """Send latency mode command.
        
        Args:
            mode: "low" for low latency, "std" for standard
            
        Returns:
            (success, message) tuple
        """
        if not self._ensure_connected():
            return False, m("connection.device_failed")
        
        try:
            if not self.capabilities.supports("latency"):
                return False, m("connection.device_failed")
            if not self.session_ready:
                return False, m("latency.disconnected")
            self._latency.write(mode == "low")
            return True, m("command.mode_sent", mode=m("mode.low" if mode == "low" else "mode.standard"))
        except Exception as e:
            return False, m("latency.failed", details=error_message(e))

    @property
    def latency_state(self):
        return self._latency.state if self.session_ready else None

    def request_latency_state(self, *, session=None, timeout=5.0):
        """Read off the listener/UI thread, without reconnecting implicitly."""
        if not self.session_ready or not self.capabilities.supports("latency"):
            raise ConnectionError(m("latency.disconnected"))
        return self._latency.read(timeout, session)
    
    def set_battery_polling_active(self, active: bool) -> None:
        """Poll only while the app is in use; refresh when it returns to foreground."""
        with self._state_lock:
            active = bool(active)
            if active == self._battery_polling_enabled:
                return
            self._battery_polling_enabled = active
            if active:
                # Coalesce quick focus/show events without flooding the device.
                self._battery_next_check_at = max(time.monotonic(), self._battery_last_request_at + 5)
            else:
                self._battery_requested_at = None
                self._battery_probe_started_at = None
                self._battery_attempts = 0

    def request_battery(self, user_initiated: bool = True) -> tuple[bool, str]:
        """Request battery status from device."""
        # User-invoked battery refresh should reopen reconnect attempts.
        if user_initiated:
            self.resume_reconnect_attempts()
        elif not self._battery_polling_enabled:
            return False, m("connection.waiting")

        if not self._ensure_connected():
            return False, m("connection.device_failed")
        
        try:
            if not self.capabilities.supports("battery"):
                return False, m("connection.device_failed")
            with self._identity_condition:
                counter = self._identity_counter
                self._identity_counter = (counter + 1) & 255
            payload = self._protocol.build_battery_request(counter)
            # Record before sending so a fast response cannot race this state.
            with self._state_lock:
                if not user_initiated and not self._battery_polling_enabled:
                    return False, m("connection.waiting")
                now = time.monotonic()
                if self._battery_requested_at is None:
                    self._battery_requested_at = now
                    self._battery_probe_started_at = now
                    self._battery_attempts = 1
                self._connection.send(payload)
                self._battery_last_request_at = now
            return True, m("battery.sent")
        except Exception as e:
            self._connection.connected = False
            return False, m("command.request_error", details=str(e))

    def _check_connection_health(self) -> None:
        """Run from the sole listener, on both incoming data and idle timeouts."""
        if not self._running or not self.connected or not self.capabilities.supports("battery"):
            return
        invalidate = False
        unresponsive = False
        exhausted = False
        with self._state_lock:
            if not self._battery_polling_enabled:
                return
            now = time.monotonic()
            requested_at = self._battery_requested_at
            if requested_at is None:
                if now < self._battery_next_check_at:
                    return
            elif now - requested_at < self._BATTERY_RESPONSE_TIMEOUT:
                return
            elif self._battery_attempts < self._BATTERY_MAX_ATTEMPTS:
                self._battery_attempts += 1
                self._battery_requested_at = now
            else:
                # Missing battery data alone does not prove a dead transport.
                exhausted = True
                unresponsive = self._last_received_at <= self._battery_probe_started_at
                invalidate = self._battery_has_value
                self._battery_has_value = False
                self._battery_requested_at = None
                self._battery_probe_started_at = None
                self._battery_attempts = 0
                self._battery_next_check_at = now + self._BATTERY_REFRESH_INTERVAL
        if invalidate:
            self._notify_battery(255, 255, 255)
        if unresponsive:
            raise ConnectionError("No response to repeated battery health probes")
        if exhausted:
            return
        success, reason = self.request_battery(user_initiated=False)
        if not success and self._battery_polling_enabled:
            raise ConnectionError(reason)
    
    def request_device_identity(self, timeout: float = 5.0, *, reconnect: bool = True) -> tuple[bool, str]:
        """Read all target info and return raw hex; run off the UI/listener thread."""
        if timeout <= 0:
            raise ValueError("Identity timeout must be positive")
        if reconnect:
            self.resume_reconnect_attempts()
        if not (self._ensure_connected() if reconnect else self.connected):
            return False, m("connection.device_failed")

        with self._identity_condition:
            if self._identity_pending is not None:
                return False, m("identity.busy")
            request = _IdentityRequest(self._identity_counter)
            self._identity_counter = (self._identity_counter + 1) & 0xFF
            self._identity_pending = request

        try:
            self._connection.send(build_identity_request(request.counter))
            with self._identity_condition:
                if not self._identity_condition.wait_for(lambda: request.completed, timeout):
                    return False, m("identity.timeout")
                if request.error:
                    return False, request.error + (f"\nRX: {request.raw_hex}" if request.raw_hex else "")
                identity = request.identity
                return True, f"{identity.describe()}\nRX: {request.raw_hex}"
        except Exception as exc:
            self._connection.connected = False
            return False, m("identity.failed", details=error_message(exc))
        finally:
            with self._identity_condition:
                if self._identity_pending is request:
                    self._identity_pending = None

    @property
    def capabilities(self):
        return resolve_capabilities(self.device_name, self.device_identity) if self.connected else DeviceCapabilities()

    @property
    def gesture_session(self):
        return self._gestures.generation

    @property
    def eq_session(self):
        return self._gestures.generation

    @property
    def eq_profiles(self):
        return eq_profiles(self.device_name, self.device_identity)

    @property
    def noise_capabilities(self):
        return noise_capabilities(self.capabilities)

    def _require_noise_backend(self):
        if not self.session_ready or not noise_backend_enabled(self.capabilities):
            raise ValueError("Device session is not ready or catalog has no ANC/transparency feature")

    def request_noise_settings(self, *, session, timeout=2.0):
        self._require_noise_backend()
        self._noise.read_aux(self.noise_capabilities, session)
        return self._noise.read(session, timeout)

    def set_adaptive_noise(self, enabled, *, session, timeout=2.0):
        self._require_noise_backend()
        return self._noise.set_adaptive(self.noise_capabilities, session, enabled, timeout)

    def set_noise_settings(self, mode, level=None, *, session, timeout=2.0):
        self._require_noise_backend()
        return self._noise.apply(self.noise_capabilities, session, mode, level, timeout)

    def request_eq_settings(self, timeout=5.0, *, session=None):
        if not self.capabilities.supports("eq"):
            return EqResult(False, message=m("eq.unsupported"))
        return self._equalizer.read(timeout, session, custom=self.capabilities.supports("custom_eq"))

    def apply_eq(self, operation, *, profile=None, bands=(), timeout=5.0, session=None):
        if operation != "profile" and not self.capabilities.supports("custom_eq"):
            return EqResult(False, message=m("eq.unsupported"))
        if not self.capabilities.supports("eq") or (operation == "profile" and (type(profile) is not int or profile not in self.eq_profiles)):
            return EqResult(False, message=m("eq.unsupported"))
        return self._equalizer.apply(operation, profile=profile, bands=bands, timeout=timeout, session=session)

    @property
    def gesture_capabilities(self):
        return gesture_capabilities(self.device_name, self.device_identity)

    def request_gesture_settings(self, timeout=5.0, *, session=None):
        """Read off the UI/listener thread; never reconnect for a stale action."""
        if not self.connected:
            return GestureResult(False, message=m("gesture.connect"))
        if not self.gesture_capabilities:
            return GestureResult(False, message=m("gesture.no_capabilities"))
        configs = tuple(dict.fromkeys(gesture_config(g) for g in self.gesture_capabilities))
        return self._gestures.read(timeout, session, configs)

    def set_gesture_assignment(self, gesture_type, side, action, timeout=5.0, *, session=None):
        """Write one side, then verify by reading the device's settings back."""
        allowed = self.gesture_capabilities.get(gesture_type, ())
        if side not in ("left", "right", "common") or type(action) is not int or action not in allowed:
            return GestureResult(False, message=m("gesture.unsupported"))
        return self._gestures.write(gesture_type, side, action, timeout, session)

    def _process_identity_data(self, data: bytes) -> None:
        self._process_identity_packets(self._identity_parser.feed(data))

    def _process_identity_packets(self, packets) -> None:
        identity = None
        with self._identity_condition:
            for packet in packets:
                request = self._identity_pending
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
                        identity = request.identity
                        self._identity = identity
                        self._last_identity = (self._bd_addr, identity)
                request.completed = True
                self._identity_condition.notify_all()
        if identity is not None:
            print(f"[Bluetooth] Device identity received: {redact(self.diagnostic_identity)}")
            if self._identity_callback:
                self._identity_callback(identity)

    def _reset_identity_state(self, reason: str) -> None:
        with self._rx_lock:
            self._reset_session_state(reason)

    def _reset_session_state(self, reason: str) -> None:
        with self._state_lock:
            invalidate = self._battery_has_value
            self._battery_has_value = False
            self._battery_requested_at = None
            self._battery_probe_started_at = None
            self._battery_attempts = 0
            self._battery_next_check_at = 0.0
        if invalidate:
            self._notify_battery(255, 255, 255)
        self._battery_parser.reset()
        self._noise_parser.reset()
        self._gestures.reset(m("gesture.connection_changed"))
        self._noise.reset()
        with self._identity_condition:
            self._identity = None
            self._identity_parser.reset()
            request = self._identity_pending
            if request is not None and not request.completed:
                request.error = reason
                request.completed = True
                self._identity_condition.notify_all()

    def send_raw(self, data: bytes) -> tuple[bool, str]:
        """Send raw bytes to device.
        
        Args:
            data: Raw bytes to send
            
        Returns:
            (success, message) tuple
        """
        if not self._ensure_connected():
            return False, m("connection.device_failed")
        
        try:
            self._connection.send(data)
            return True, m("command.raw_sent", data=data.hex())
        except Exception as e:
            self._connection.connected = False
            return False, m("command.send_error", details=str(e))
    
    def _ensure_connected(self) -> bool:
        """Ensure connected, attempting to connect if not."""
        return self._running and (self._connection.connected or self.connect())

    def reconnect(self, force_rediscovery: bool = False) -> bool:
        """Reconnect to the device, optionally forcing MAC rediscovery."""
        with self._connect_lock:
            if not self._running:
                return False
            # A queued UI retry must not disconnect a connection just established
            # by the listener (or another command).
            if self._connection.connected:
                return True
            self._reset_identity_state(m("identity.disconnected"))
            self._connection.disconnect()
            if force_rediscovery:
                self._bd_addr = None
                self._device_name = ""
            self._notify_connection_event("reconnecting")
            return self.connect()

    def select_device(self, address):
        """Only accept an address offered by the latest eligible discovery."""
        with self._connect_lock:
            device = next((item for item in self._device_candidates if item.address == address), None)
            if device is None:
                return False
            self._connection.disconnect()
            self._reset_identity_state(m("identity.connection_changed"))
            self._bd_addr, self._device_name = device.address, device.name
            set_selected_bluetooth_address(device.address)
            self.resume_reconnect_attempts()
            return self.connect()
    
    def on_connect_setup(self):
            """Send a sequence of packets on connection."""
            if not self.capabilities.supports("battery"):
                return
            legacy_setup = (not self._connection.session_authenticated and
                            " ".join(self._device_name.split()).casefold() == "redmi buds 6 play")
            packets = [] if not legacy_setup else [
                "fedcba04510003000301ef"
            ]
            for packet_hex in packets:
                test_bytes = bytes.fromhex(packet_hex)
                print(self.send_raw(test_bytes))
                time.sleep(0.1)
            # Also request battery after sending packets
            time.sleep(1)
            self.request_battery(user_initiated=False)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Listener
    # ─────────────────────────────────────────────────────────────────────────
    def listen(self) -> None:
        """Main listener loop for incoming data."""
        last_packet_size = 0
        disconnected_since: Optional[float] = None
        
        while self._running:
            if not self._connection.connected:
                with self._state_lock:
                    reconnect_paused = self._reconnect_paused
                    retry_at = self._reconnect_retry_at

                if reconnect_paused:
                    if time.monotonic() >= retry_at:
                        self._reset_reconnect_state()
                    else:
                        time.sleep(1)
                    continue

                if disconnected_since is None:
                    disconnected_since = time.monotonic()

                force_rediscovery = (
                    time.monotonic() - disconnected_since >= self._STALE_CONNECTION_TIMEOUT
                )
                if force_rediscovery:
                    self._update_status(m("connection.stale"), "orange")

                if not self.reconnect(force_rediscovery=force_rediscovery):
                    attempts, reached_limit = self._record_reconnect_failure()
                    if reached_limit:
                        self._update_status(m("connection.retry_limit"), "red")
                        self._notify_connection_state(
                            "failed", self._last_connection_failure or m("connection.retry_limit"))
                        self._notify_connection_event("reconnect_failed_limit")
                    else:
                        self._update_status(
                            m("connection.retrying", attempts=attempts, maximum=self._max_reconnect_attempts, delay=RECONNECT_DELAY),
                            "orange"
                        )
                    for remaining in range(RECONNECT_DELAY, 0, -1):
                        if not self._running or self.connected:
                            break
                        if not reached_limit:
                            self._notify_connection_state("retrying", m(
                                "connection.retrying", attempts=attempts,
                                maximum=self._max_reconnect_attempts, delay=remaining))
                        time.sleep(1)
                else:
                    disconnected_since = None
                    last_packet_size = 0
                continue
            
            try:
                self._check_connection_health()
                last_packet_size = self._process_data(last_packet_size)
                disconnected_since = None
            except socket.timeout:
                # The next loop checks the health deadline even on idle sockets.
                continue
            except Exception as exc:
                if self._running and self._connection.connected:
                    self._report_connection_error(exc, "bluetooth_receive")
                self._handle_disconnect()
    
    def _process_data(self, last_packet_size: int) -> int:
        """Process incoming data packet."""
        session = self.eq_session
        transport = self._connection.result
        try:
            data = self._connection.receive()
        except OSError:
            if session != self.eq_session or transport is not self._connection.result:
                return last_packet_size
            raise
        if session != self.eq_session or transport is not self._connection.result:
            return last_packet_size
        if not data:
            raise ConnectionError("Received zero bytes from RFCOMM socket")
        with self._state_lock:
            self._last_received_at = time.monotonic()

        packet_size = len(data)
        print(f"Received data size: {packet_size}")
        with self._rx_lock:
            if session != self.eq_session or not self.connected:
                return packet_size
            packets = self._noise_parser.feed(data)
            self._process_identity_packets(packets)
            config_response = self._gestures.feed_packets(packets)
            statuses = self._battery_parser.feed_packets(packets)
            capture_noise = noise_backend_enabled(self.capabilities)
            for packet in packets:
                if packet.opcode in (0x50, 0x51):
                    auth = self._connection.auth_session
                    if isinstance(auth, CommandAuthSession) and auth.authenticated:
                        auth.feed(bytes.fromhex(packet.raw_hex))
                    continue
                if capture_noise:
                    record("RX", bytes.fromhex(packet.raw_hex))
                if not is_supported_target(packet.flags):
                    continue
                if packet.opcode == 0xF4:
                    offset = 1 if packet.flags & 0x80 else 2
                    if len(packet.payload) < offset or (offset == 2 and packet.payload[0]):
                        continue
                    try:
                        records = parse_config_records(packet.payload[offset:])
                    except ValueError:
                        continue
                    self._gestures.notify(session, records)
                    self._latency.notify(session, records)
                    eq = self._equalizer.notify(session, records)
                    if 2 in records or 80 in records:
                        try:
                            self._gestures._last_read = parse_gesture_records(packet.payload[offset:], physical=True)
                        except ValueError:
                            pass
                    self._noise.notify_aux(session, records)
                    try:
                        state = parse_noise_notification(packet)
                    except ValueError:
                        state = None
                    if state is not None:
                        state = self._noise.enrich(session, state)
                        self._noise.notify(session, state)
                        if self.noise_callback:
                            self.noise_callback(session, state)
                    elif 12 in records or 37 in records:
                        state = self._noise.current_state(session)
                        if state is not None and self.noise_callback:
                            self.noise_callback(session, state)
                    if self.config_callback:
                        self.config_callback(session, records, eq)
                elif packet.opcode == 0x0E:
                    from .packets.rcsp import parse_info_fields
                    try:
                        if not packet.flags & 0x80 or not packet.payload:
                            continue
                        parse_info_fields(packet.payload[1:])
                    except ValueError:
                        continue
                else:
                    continue
                # A single router owns notification ACKs. Bit 6 requests one.
                if packet.flags & 0x80 and packet.flags & 0x40:
                    self._connection.send(bytes.fromhex("fe dc ba 04") +
                                          bytes((packet.opcode, 0, 2, 0, packet.payload[0], 0xEF)))

            if statuses:
                with self._state_lock:
                    self._battery_requested_at = None
                    self._battery_probe_started_at = None
                    self._battery_attempts = 0
                    self._battery_has_value = True
                    self._battery_next_check_at = time.monotonic() + self._BATTERY_REFRESH_INTERVAL
                for status in statuses:
                    values = []
                    for label, raw in (("left", status.left), ("right", status.right), ("case", status.case)):
                        percent = raw - 128 if raw >= 128 else raw
                        value = "unknown" if raw == 255 or not 0 <= percent <= 100 else f"{percent}%"
                        if value != "unknown" and raw >= 128:
                            value += " (charging)"
                        values.append(f"{label}={value} [raw={raw}]")
                    print("[Bluetooth] Battery received: " + "; ".join(values))
                    self._notify_battery(status.left, status.right, status.case)
            
            # Check for mode acknowledgment
            elif not config_response and self._protocol.is_mode_ack_packet(packet_size):
                if last_packet_size != packet_size:
                    self._trigger_battery_check()
            
        return packet_size
    
    def _handle_disconnect(self) -> None:
        """Handle connection loss."""
        if not self._running:
            return
        self._reset_identity_state(m("identity.disconnected"))
        self._connection.disconnect()
        self._update_status(m("connection.lost"), "red")
        self._notify_connection_state(
            "failed", m("connection.disconnected_reason")
        )
        self._notify_connection_event("disconnected")
        time.sleep(2)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Cleanup
    # ─────────────────────────────────────────────────────────────────────────
    def stop(self) -> None:
        """Stop the controller."""
        self._running = False
        try:
            self._connection.stop()
        finally:
            self._reset_identity_state(m("identity.stopped"))
