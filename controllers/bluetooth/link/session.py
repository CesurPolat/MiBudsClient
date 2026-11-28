"""Link lifecycle, peer selection and reconnect policy for Bluetooth controllers."""

import socket
import threading
import time
from abc import ABC, abstractmethod
from functools import partial

from utils.app.i18n import message as m
from utils.app.user_preferences import get_selected_bluetooth_address, set_selected_bluetooth_address
from utils.diagnostics.error_reports import redact

from ...catalog.capabilities import resolve_capabilities
from ...noise.capture import record
from ...noise.protocol import noise_backend_enabled
from ..auth.auth_session import AuthPolicy
from .connection import BluetoothConnection
from .discovery import BluetoothDiscovery
from .failures import connection_failure_reason, report_connection_error
from .sdp import ConnectionCancelled


RECONNECT_DELAY = 5


class BluetoothSession(ABC):
    """Own the link while the controller handles device-specific commands and data."""

    _STALE_CONNECTION_TIMEOUT = 12
    _RECONNECT_COOLDOWN = 120

    def __init__(self, *, bd_addr, auth_policy, status_callback, connection_event_callback,
                 connection_state_callback, error_callback):
        self._connection = BluetoothConnection(on_send=partial(record, "TX"))
        self._auth_policy = AuthPolicy(auth_policy) if auth_policy is not None else None
        self.device_candidates_callback = None
        self._device_candidates = ()
        self._bd_addr = bd_addr
        self._device_name = ""
        self._device_check = {"state": "unknown"}
        self._discovery_devices = []
        self._running = True
        self._connect_lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._max_reconnect_attempts = 5
        self._reconnect_attempts = 0
        self._reconnect_paused = False
        self._reconnect_retry_at = 0.0
        self._last_connection_event = None
        self._last_connection_failure = ""
        self._status_callback = status_callback
        self._connection_event_callback = connection_event_callback
        self._connection_state_callback = connection_state_callback
        self._error_callback = error_callback

    @property
    def connection(self) -> BluetoothConnection:
        return self._connection

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

    def _notify_connection_state(self, state: str, reason: str = "") -> None:
        if state != "retrying":  # Do not repeat the countdown every second.
            print(redact(f"[Bluetooth] state={state} reason={reason}"))
        if state == "failed" and reason:
            self._last_connection_failure = reason
        elif state == "connected":
            self._last_connection_failure = ""
        if self._connection_state_callback:
            self._connection_state_callback(state, reason)

    def _update_status(self, text: str, color: str = "black") -> None:
        """Send status update to UI."""
        if self._status_callback:
            self._status_callback(text, color)

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
                        reason = m("connection.choose_device" if devices else "connection.no_device")
                        self._notify_connection_state("failed", reason)
                        self._update_status(reason, "red")
                        return False
                    self._bd_addr = device.address
                    self._device_name = device.name
                    set_selected_bluetooth_address(device.address)
                self._device_check = BluetoothDiscovery.connection_state(self._bd_addr)
                print(f"[Bluetooth] Device check: {redact(self._device_check)}")
                self._reset_session_state(m("identity.connection_changed"))
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
                self._mark_received()
                self._reset_reconnect_state()
                self._notify_connection_state("connected")
                self._notify_connection_event("connected")
                self.on_connect_setup()
                return True
            except Exception as e:
                if not self._running or isinstance(e, ConnectionCancelled):
                    return False
                self._connection.connected = False
                if isinstance(e, OSError) and self._peer_is_disconnected():
                    reason = m("connection.no_device")
                    self._update_status(reason, "red")
                    self._notify_connection_state("failed", reason)
                    return False
                self._update_status(m("connection.failure_details", details=str(e)), "red")
                reason = connection_failure_reason(e, self._connection.stage)
                self._notify_connection_state("failed", m("connection.technical", reason=reason, details=str(e) or type(e).__name__))
                self._report_connection_error(e, "bluetooth_connect")
                return False

    def _peer_is_disconnected(self) -> bool:
        if not self._bd_addr:
            return False
        self._device_check = BluetoothDiscovery.connection_state(self._bd_addr)
        return self._device_check.get("state") == "disconnected"

    def _report_connection_error(self, error, action):
        report_connection_error(
            error, action, connection=self._connection, device_name=self._device_name,
            device_check=self._device_check, discovered_devices=self._discovery_devices,
            identity=self.diagnostic_identity, on_error=self._error_callback,
        )

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
            self._reset_session_state(m("identity.disconnected"))
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
            self._reset_session_state(m("identity.connection_changed"))
            self._bd_addr, self._device_name = device.address, device.name
            set_selected_bluetooth_address(device.address)
            self.resume_reconnect_attempts()
            return self.connect()

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
                    failure = self._last_connection_failure
                    no_device = getattr(failure, "key", None) == "connection.no_device"
                    if reached_limit:
                        self._update_status(failure if no_device else m("connection.retry_limit"), "red")
                        self._notify_connection_state(
                            "failed", failure or m("connection.retry_limit"))
                        self._notify_connection_event("reconnect_failed_limit")
                    elif not no_device:
                        self._update_status(
                            m("connection.retrying", attempts=attempts, maximum=self._max_reconnect_attempts, delay=RECONNECT_DELAY),
                            "orange"
                        )
                    for remaining in range(RECONNECT_DELAY, 0, -1):
                        if not self._running or self.connected:
                            break
                        if not reached_limit:
                            self._notify_connection_state("retrying", failure if no_device else m(
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
                peer_disconnected = False
                if self._running and self._connection.connected:
                    peer_disconnected = isinstance(exc, OSError) and self._peer_is_disconnected()
                    if not peer_disconnected:
                        self._report_connection_error(exc, "bluetooth_receive")
                self._handle_disconnect(peer_disconnected=peer_disconnected)

    def _handle_disconnect(self, *, peer_disconnected: bool = False) -> None:
        """Handle connection loss."""
        if not self._running:
            return
        self._reset_session_state(m("identity.disconnected"))
        self._connection.disconnect()
        reason = m("connection.no_device" if peer_disconnected else "connection.disconnected_reason")
        self._update_status(reason if peer_disconnected else m("connection.lost"), "red")
        self._notify_connection_state("failed", reason)
        self._notify_connection_event("disconnected")
        time.sleep(2)

    def stop(self) -> None:
        """Stop the controller."""
        self._running = False
        try:
            self._connection.stop()
        finally:
            self._reset_session_state(m("identity.stopped"))

    @property
    @abstractmethod
    def diagnostic_identity(self) -> dict:
        """Return identity metadata belonging to the selected peer."""

    @abstractmethod
    def _reset_session_state(self, reason: str) -> None:
        """Clear device state and unblock pending operations."""

    @abstractmethod
    def _mark_received(self) -> None:
        """Record the start of transport activity for health checks."""

    @abstractmethod
    def on_connect_setup(self) -> None:
        """Run device setup after publishing the connection event."""

    @abstractmethod
    def _check_connection_health(self) -> None:
        """Run health checks on the listener thread."""

    @abstractmethod
    def _process_data(self, last_packet_size: int) -> int:
        """Read one chunk from the link and return its size."""
