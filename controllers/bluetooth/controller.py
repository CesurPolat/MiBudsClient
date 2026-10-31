"""Main Bluetooth Controller for Mi Buds."""

from utils.i18n import message as m, error_message

import socket
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .capabilities import resolve_capabilities, DeviceCapabilities
from .connection import BluetoothConnection
from .auth_session import AuthPolicy, profile_auth_policy
from .discovery import BluetoothDiscovery
from .protocol import BudsProtocol
from .battery_stream import BatteryStreamParser
from .gesture_transport import GestureTransport
from .eq_transport import EqTransport
from .noise import noise_capabilities, noise_backend_enabled, parse_noise_notification
from .noise_transport import NoiseTransport
from .equalizer import EqResult, eq_profiles
from .gestures import GestureResult, gesture_capabilities
from .constants import RECONNECT_DELAY
from .rcsp import DeviceIdentity, RcspStreamParser, build_identity_request, parse_identity_fields


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
    ):
        self._connection = BluetoothConnection()
        self._auth_policy = AuthPolicy(auth_policy) if auth_policy is not None else None
        self._protocol = BudsProtocol()
        self._battery_parser = BatteryStreamParser()
        self._gestures = GestureTransport(self._connection)
        self._equalizer = EqTransport(self._gestures)
        self._noise = NoiseTransport(self._gestures)
        self._noise_parser = RcspStreamParser()
        self.noise_callback = None
        self._bd_addr = bd_addr
        self._device_name = ""
        self._running = True
        self._connect_lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._identity_condition = threading.Condition()
        self._identity_parser = RcspStreamParser()
        self._identity_pending: Optional[_IdentityRequest] = None
        self._identity_counter = 0x90
        self._identity: Optional[DeviceIdentity] = None
        self._identity_callback = identity_callback
        self._max_reconnect_attempts = 5
        self._reconnect_attempts = 0
        self._reconnect_paused = False
        self._last_connection_event: Optional[str] = None
        
        # Callbacks
        self._status_callback = status_callback
        self._battery_callback = battery_callback
        self._check_battery_callback = check_battery_callback
        self._connection_event_callback = connection_event_callback
        self._connection_state_callback = connection_state_callback

    def _notify_connection_state(self, state: str, reason: str = "") -> None:
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

    def _record_reconnect_failure(self) -> tuple[int, bool]:
        with self._state_lock:
            self._reconnect_attempts += 1
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                self._reconnect_paused = True
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
            if self._connection.connected:
                return True

            self._notify_connection_state("connecting")
            try:
                if not self._bd_addr:
                    device = BluetoothDiscovery.get_connected_device()
                    if not device or not device.address:
                        reason = m("connection.no_catalog")
                        self._notify_connection_state("failed", reason)
                        self._update_status(m("connection.no_device"), "red")
                        return False
                    self._bd_addr = device.address
                    self._device_name = device.name
                self._reset_identity_state(m("identity.connection_changed"))
                policy = self._auth_policy or profile_auth_policy(self._device_name)
                # Test sessions require an explicit model AND explicit auth policy.
                test_caps = resolve_capabilities(self._device_name)
                if self._auth_policy is None and noise_backend_enabled(test_caps):
                    test_policy = os.environ.get("MIBUDS_EXPERIMENTAL_AUTH", "")
                    if test_policy in (AuthPolicy.COMMAND.value, AuthPolicy.DIRECT.value):
                        policy = AuthPolicy(test_policy)
                self._connection.connect(self._bd_addr, device_name=self._device_name, session_policy=policy)
                if noise_backend_enabled(test_caps):
                    from .noise_capture import record
                    result = self._connection.result
                    record("SESSION", model=test_caps.model, device_name=self._device_name,
                           service_uuid=result.service_uuid, channel=result.channel,
                           resolution_source=result.resolution_source,
                           auth_policy=policy.value, authenticated=self.session_authenticated)
                self._update_status(m("connection.connected"), "blue")
                self._reset_reconnect_state()
                self._notify_connection_state("connected")
                self._notify_connection_event("connected")
                self.on_connect_setup()
                return True
            except Exception as e:
                self._connection.connected = False
                self._update_status(m("connection.failure_details", details=str(e)), "red")
                if isinstance(e, (TimeoutError, socket.timeout)):
                    reason = m("connection.timeout")
                elif isinstance(e, PermissionError):
                    reason = m("connection.permission")
                else:
                    reason = m("connection.establish_failed")
                self._notify_connection_state("failed", m("connection.technical", reason=reason, details=str(e) or type(e).__name__))
                return False
    
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
            payload = self._protocol.build_mode_command(mode)
            self._connection.send(payload)
            return True, m("command.mode_sent", mode=m("mode.low" if mode == "low" else "mode.standard"))
        except Exception as e:
            self._connection.connected = False
            return False, m("command.send_error", details=str(e))
    
    def request_battery(self, user_initiated: bool = True) -> tuple[bool, str]:
        """Request battery status from device."""
        # User-invoked battery refresh should reopen reconnect attempts.
        if user_initiated:
            self.resume_reconnect_attempts()

        if not self._ensure_connected():
            return False, m("connection.device_failed")
        
        try:
            if not self.capabilities.supports("battery"):
                return False, m("connection.device_failed")
            payload = self._protocol.build_battery_request()
            self._connection.send(payload)
            return True, m("battery.sent")
        except Exception as e:
            self._connection.connected = False
            return False, m("command.request_error", details=str(e))
    
    def request_device_identity(self, timeout: float = 5.0) -> tuple[bool, str]:
        """Read all target info and return raw hex; run off the UI/listener thread."""
        if timeout <= 0:
            raise ValueError("Identity timeout must be positive")
        self.resume_reconnect_attempts()
        if not self._ensure_connected():
            return False, m("connection.device_failed")

        with self._identity_condition:
            if self._identity_pending is not None:
                return False, m("identity.busy")
            request = _IdentityRequest(self._identity_counter)
            self._identity_counter = (self._identity_counter + 1) & 0xFF
            self._identity_pending = request
            # Do not reuse an incomplete frame from an earlier, timed-out query.
            self._identity_parser.reset()

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
            raise ValueError("ANC backend requires model-specific hardware validation")

    def request_noise_settings(self, *, session, timeout=2.0):
        self._require_noise_backend()
        return self._noise.read(session, timeout)

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
        if not self.capabilities.supports("eq") or (operation == "profile" and profile not in self.eq_profiles):
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
        return self._gestures.read(timeout, session)

    def set_gesture_assignment(self, gesture_type, side, action, timeout=5.0, *, session=None):
        """Write one side, then verify by reading the device's settings back."""
        allowed = self.gesture_capabilities.get(gesture_type, ())
        if side not in ("left", "right") or type(action) is not int or action not in allowed:
            return GestureResult(False, message=m("gesture.unsupported"))
        return self._gestures.write(gesture_type, side, action, timeout, session)

    def _process_identity_data(self, data: bytes) -> None:
        identity = None
        with self._identity_condition:
            for packet in self._identity_parser.feed(data):
                request = self._identity_pending
                if request is None or request.completed:
                    continue
                if packet.flags & 0x80 or packet.opcode != 0x02 or len(packet.payload) < 2:
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
                request.completed = True
                self._identity_condition.notify_all()
        if identity is not None and self._identity_callback:
            self._identity_callback(identity)

    def _reset_identity_state(self, reason: str) -> None:
        self._battery_parser.reset()
        self._noise_parser.reset()
        self._gestures.reset(m("gesture.connection_changed"))
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
        return self._connection.connected or self.connect()

    def reconnect(self, force_rediscovery: bool = False) -> bool:
        """Reconnect to the device, optionally forcing MAC rediscovery."""
        with self._connect_lock:
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
    
    def on_connect_setup(self):
            """Send a sequence of packets on connection."""
            if not self.capabilities.supports("battery"):
                return
            packets = [] if self._connection.session_authenticated else [
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
        last_data_received_at = time.monotonic()
        disconnected_since: Optional[float] = None
        
        while self._running:
            if not self._connection.connected:
                with self._state_lock:
                    reconnect_paused = self._reconnect_paused

                if reconnect_paused:
                    time.sleep(RECONNECT_DELAY)
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
                        self._notify_connection_event("reconnect_failed_limit")
                    else:
                        self._update_status(
                            m("connection.retrying", attempts=attempts, maximum=self._max_reconnect_attempts, delay=RECONNECT_DELAY),
                            "orange"
                        )
                    time.sleep(RECONNECT_DELAY)
                else:
                    disconnected_since = None
                    last_data_received_at = time.monotonic()
                continue
            
            try:
                last_packet_size = self._process_data(last_packet_size)
                last_data_received_at = time.monotonic()
                disconnected_since = None
            except socket.timeout:
                # Keep idle connections without forcing periodic battery probes.
                # Reconnect is handled only on explicit send/receive failures.
                continue
            except Exception:
                self._handle_disconnect()
    
    def _process_data(self, last_packet_size: int) -> int:
        """Process incoming data packet."""
        data = self._connection.receive()
        if not data:
            raise ConnectionError("Received zero bytes from RFCOMM socket")

        packet_size = len(data)
        print(f"Received data size: {packet_size}")
        self._process_identity_data(data)
        config_response = self._gestures.feed(data)
        if noise_backend_enabled(self.capabilities):
            from .noise_capture import record
            record("RX", data)
            for packet in self._noise_parser.feed(data):
                if packet.flags & 7 not in (4, 7):
                    continue
                try:
                    state = parse_noise_notification(packet)
                except ValueError:
                    continue
                if state is not None:
                    # Respond only if the peer explicitly requests an ACK.
                    if packet.flags & 0x80 and packet.flags & 0x40:
                        self._connection.send(bytes.fromhex("fe dc ba 04 f4 00 02") +
                                              bytes((0, packet.payload[0], 0xEF)))
                    if self.noise_callback:
                        self.noise_callback(self.eq_session, state)

        # Check for battery data
        statuses = self._battery_parser.feed(data)
        if statuses:
            for status in statuses:
                self._notify_battery(status.left, status.right, status.case)
        
        # Check for mode acknowledgment
        elif not config_response and self._protocol.is_mode_ack_packet(packet_size):
            if last_packet_size != packet_size:
                self._trigger_battery_check()
        
        return packet_size
    
    def _handle_disconnect(self) -> None:
        """Handle connection loss."""
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
        self._reset_identity_state(m("identity.stopped"))
        self._connection.disconnect()
