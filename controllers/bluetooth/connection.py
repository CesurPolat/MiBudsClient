"""Bluetooth socket connection handler."""

import socket
import os
import threading
import logging
import time
from dataclasses import dataclass
from typing import Optional

from .sdp import PlatformBackend, SERVICE_UUIDS, ConnectionCancelled
from .auth_session import AuthPolicy, AuthError, CommandAuthSession
from .raw_auth import RawAuthSession

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
        self._stopped = False
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
        """Socket opened, including while authentication is pending."""
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
                if self._stopped:
                    raise ConnectionCancelled("Controller stopped")
                self._cancel = cancel
            deadline = time.monotonic() + timeout
            last_error = None
            resolved = False
            source = getattr(self._backend, "resolution_source", None)
            # Older injected backends may not provide platform metadata.
            source = source if isinstance(source, str) else "windows_sdp"

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
                    log.warning("RFCOMM stage=resolution uuid=%s source=%s error=%s", uuid, source, exc)
                    continue
                if channel is None:
                    log.info("RFCOMM stage=resolution uuid=%s channel=None", uuid)
                    continue
                if type(channel) is not int or not 1 <= channel <= 30:
                    raise ValueError("Backend returned invalid RFCOMM channel")
                resolved = True
                try:
                    result = open_channel(uuid, channel, source)
                except ConnectionCancelled:
                    raise
                except OSError as exc:
                    last_error = exc
                    log.warning("RFCOMM stage=connection uuid=%s channel=%s source=%s error=%s", uuid, channel, source, exc)
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
        prefetched = bytearray()
        try:
            if policy == AuthPolicy.AUTO:
                if result.service_uuid == SERVICE_UUIDS[0]:
                    policy = AuthPolicy.COMMAND
                elif result.service_uuid in SERVICE_UUIDS[1:]:
                    policy = AuthPolicy.RAW
                elif result.service_uuid is None and result.resolution_source == "profile_fallback":
                    # The existing fallback is exclusively the legacy 6 Play path.
                    policy = AuthPolicy.DIRECT
                else:
                    raise AuthError("Cannot select authentication without a known service UUID")
            if policy == AuthPolicy.UNKNOWN:
                raise AuthError(f"Unsupported authentication method for selected service: {policy.value}")
            if policy in (AuthPolicy.COMMAND, AuthPolicy.RAW):
                if policy == AuthPolicy.COMMAND and result.service_uuid != SERVICE_UUIDS[0]:
                    raise AuthError("command_auth requires a resolved MIUI SPP service")
                if policy == AuthPolicy.RAW and result.service_uuid not in SERVICE_UUIDS[1:]:
                    raise AuthError("raw_auth requires a resolved XiaoAI or standard SPP service")
                sock = result.socket
                session_type = CommandAuthSession if policy == AuthPolicy.COMMAND else RawAuthSession
                session = session_type(sock.sendall)
                with self._state_lock:
                    if cancel.is_set():
                        raise ConnectionCancelled("Auth cancelled")
                    self.auth_session = session
                print(f"[Bluetooth] Auth policy={policy.value} state=authenticating")
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
                    prefetched.extend(b"".join(session.feed(data)))
                sock.settimeout(SOCKET_TIMEOUT)
            with self._state_lock:
                if cancel.is_set():
                    raise ConnectionCancelled("Session cancelled")
                self._prefetched = bytes(prefetched)
                self.session_authenticated = policy in (AuthPolicy.COMMAND, AuthPolicy.RAW)
                self.session_ready = policy in (AuthPolicy.COMMAND, AuthPolicy.RAW, AuthPolicy.DIRECT)
                self._connected = True
            if policy is not None:
                print(f"[Bluetooth] Session policy={policy.value} ready={self.session_ready} authenticated={self.session_authenticated}")
            return result
        except BaseException:
            print("[Bluetooth] Session failed; closing transport (no auth fallback)")
            self.disconnect()
            raise

    def stop(self) -> None:
        """Permanently reject queued connects and cancel the current session."""
        with self._state_lock:
            self._stopped = True
        self.disconnect()

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
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
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
            if self._sock is None:
                raise ConnectionError("RFCOMM socket is unavailable")
            self._sock.sendall(data)
            if os.environ.get("MIBUDS_ANC_CAPTURE"):
                from .noise_capture import record
                record("TX", data)
    
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
