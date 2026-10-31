"""Bluetooth socket connection handler."""

import socket
import threading
import logging
import time
from dataclasses import dataclass
from typing import Optional

from .sdp import PlatformBackend, SERVICE_UUIDS, ConnectionCancelled
from .auth_session import AuthPolicy, AuthError, CommandAuthSession

from .constants import RFCOMM_PORT, SOCKET_TIMEOUT, RECV_BUFFER_SIZE


@dataclass(frozen=True)
class ConnectionResult:
    socket: object
    service_uuid: str | None
    channel: int
    resolution_source: str


log = logging.getLogger(__name__)


class BluetoothConnection:
    """Manages Bluetooth socket connection."""
    
    def __init__(self, backend=None):
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._connected = False
        self._backend = backend if backend is not None else PlatformBackend()
        self._state_lock = threading.Lock()
        self._connect_lock = threading.Lock()
        self._cancel = threading.Event()
        self.result: ConnectionResult | None = None
        self.session_ready = False
        self.session_authenticated = False
        self.auth_session = None
        self._prefetched = b""
    
    @property
    def connected(self) -> bool:
        """Check if currently connected."""
        return self._connected

    @property
    def transport_connected(self) -> bool:
        """Socket opened, including while command authentication is pending."""
        return self._sock is not None and self.result is not None
    
    @connected.setter
    def connected(self, value: bool) -> None:
        """Set connection status."""
        self._connected = value
    
    def connect(self, address: str, device_name: str = "", timeout: float = 18,
                *, session_policy: AuthPolicy | str | None = None) -> ConnectionResult:
        """Resolve each exact service on this peer; keep the legacy 6 Play path.

        Called by the controller's background connection worker. A disconnect
        cancels both SDP and a pending socket. No authentication is inferred.
        """
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        if session_policy is not None:
            session_policy = AuthPolicy(session_policy)
        with self._connect_lock:
            self.disconnect()
            cancel = threading.Event()
            with self._state_lock:
                self._cancel = cancel
            deadline = time.monotonic() + timeout
            last_error = None
            resolved = False

            def budget(limit):
                if cancel.is_set():
                    raise ConnectionCancelled("Connection cancelled")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("RFCOMM connection budget exhausted")
                return min(limit, remaining)

            def open_channel(uuid, channel, source):
                connect_timeout = budget(SOCKET_TIMEOUT)
                log.info("RFCOMM stage=connection uuid=%s channel=%s source=%s", uuid, channel, source)
                sock = self._backend.create_rfcomm_socket()
                try:
                    with self._state_lock:
                        if cancel.is_set():
                            raise ConnectionCancelled("Connection cancelled")
                        self._sock = sock
                    sock.settimeout(connect_timeout)
                    sock.connect((address, channel))
                    budget(SOCKET_TIMEOUT)
                    with self._state_lock:
                        if cancel.is_set():
                            raise ConnectionCancelled("Connection cancelled")
                        result = ConnectionResult(sock, uuid, channel, source)
                        self.result = result
                        # Publish only after session establishment, so the listener
                        # cannot race the temporary auth reader.
                        self._connected = session_policy is None
                    log.info("RFCOMM connected uuid=%s channel=%s source=%s", uuid, channel, source)
                    # The F12 debug console captures stdout; INFO logging may be disabled.
                    method = (
                        "eski yontem (6 Play kanal 6 yedegi)"
                        if source == "profile_fallback"
                        else "yeni yontem (SDP servis kesfi)"
                    )
                    print(
                        f"[Bluetooth] Baglanti basarili: {method}; "
                        f"kanal={channel}; service_uuid={uuid}; resolution_source={source}"
                    )
                    return result
                except BaseException:
                    sock.close()
                    with self._state_lock:
                        if self._sock is sock:
                            self._sock = None
                    raise

            for uuid in SERVICE_UUIDS:
                lookup_timeout = budget(4)
                try:
                    channel = self._backend.resolve_rfcomm_channel(address, uuid, lookup_timeout, cancel)
                except ConnectionCancelled:
                    raise
                except OSError as exc:
                    last_error = exc
                    log.warning("RFCOMM stage=resolution uuid=%s source=windows_sdp error=%s", uuid, exc)
                    continue
                if channel is None:
                    log.info("RFCOMM stage=resolution uuid=%s channel=None", uuid)
                    continue
                if type(channel) is not int or not 1 <= channel <= 30:
                    raise ValueError("Backend returned invalid RFCOMM channel")
                resolved = True
                try:
                    result = open_channel(uuid, channel, "windows_sdp")
                except ConnectionCancelled:
                    raise
                except OSError as exc:
                    last_error = exc
                    log.warning("RFCOMM stage=connection uuid=%s channel=%s source=windows_sdp error=%s", uuid, channel, exc)
                    continue
                return self._activate_session(result, session_policy, cancel)
            # Only when SDP could not resolve any service. Never label this FD2D.
            if not resolved and " ".join(device_name.split()).casefold() == "redmi buds 6 play":
                result = open_channel(None, RFCOMM_PORT, "profile_fallback")
                return self._activate_session(result, session_policy, cancel)
            budget(SOCKET_TIMEOUT)
            raise ConnectionError("No usable RFCOMM service for selected device") from last_error

    def _activate_session(self, result, policy, cancel):
        """Single reader handoff: auth here, existing listener after publication."""
        try:
            if policy in (AuthPolicy.UNKNOWN, AuthPolicy.RAW):
                raise AuthError(f"Unsupported session policy: {policy.value}")
            if policy == AuthPolicy.COMMAND:
                if result.service_uuid != SERVICE_UUIDS[0]:
                    raise AuthError("command_auth requires a resolved MIUI SPP service; raw auth is unsupported")
                sock = result.socket
                session = CommandAuthSession(sock.sendall)
                with self._state_lock:
                    if cancel.is_set():
                        raise ConnectionCancelled("Auth cancelled")
                    self.auth_session = session
                print("[Bluetooth] Auth policy=command_auth state=authenticating")
                session.start()
                while not session.authenticated:
                    if cancel.is_set():
                        raise ConnectionCancelled("Auth cancelled")
                    session.tick()
                    sock.settimeout(0.1)
                    try:
                        data = sock.recv(RECV_BUFFER_SIZE)
                    except socket.timeout:
                        continue
                    if cancel.is_set():
                        raise ConnectionCancelled("Auth cancelled")
                    if not data:
                        raise AuthError("Connection closed during authentication")
                    self._prefetched += b"".join(session.feed(data))
                sock.settimeout(SOCKET_TIMEOUT)
            with self._state_lock:
                if cancel.is_set():
                    raise ConnectionCancelled("Session cancelled")
                self.session_authenticated = policy == AuthPolicy.COMMAND
                self.session_ready = policy in (AuthPolicy.COMMAND, AuthPolicy.DIRECT)
                self._connected = True
            if policy is not None:
                print(f"[Bluetooth] Session policy={policy.value} ready={self.session_ready} authenticated={self.session_authenticated}")
            return result
        except BaseException:
            print("[Bluetooth] Session failed; closing transport (no auth fallback)")
            self.disconnect()
            raise

    def disconnect(self) -> None:
        """Cancel pending work and close the current transport."""
        with self._state_lock:
            self._cancel.set()
            self._connected = False
            self.result = None
            self.session_ready = False
            self.session_authenticated = False
            self._prefetched = b""
            session, self.auth_session = self.auth_session, None
            sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if session is not None:
            session.abort("Transport disconnected")

    def send(self, data: bytes) -> None:
        """Send data to device.
        
        Args:
            data: Bytes to send
            
        Raises:
            Exception: If send fails
        """
        with self._lock:
            if not self._connected:
                raise ConnectionError("Transport session is not ready")
            if self._sock:
                self._sock.sendall(data)
    
    def receive(self) -> bytes:
        """Receive data from device.
        
        Returns:
            Received bytes
            
        Raises:
            socket.timeout: If no data available
            Exception: If receive fails
        """
        if not self._connected:
            raise ConnectionError("Transport session is not ready")
        if self._prefetched:
            data, self._prefetched = self._prefetched, b""
            return data
        if self._sock:
            data = self._sock.recv(RECV_BUFFER_SIZE)
            if not data:
                self.disconnect()
            return data
        return b""
