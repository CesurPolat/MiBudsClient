"""Bluetooth socket connection handler."""

import socket
import threading
import logging
import time
from dataclasses import dataclass
from typing import Optional

from .sdp import PlatformBackend, SERVICE_UUIDS, ConnectionCancelled

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
    
    @property
    def connected(self) -> bool:
        """Check if currently connected."""
        return self._connected
    
    @connected.setter
    def connected(self, value: bool) -> None:
        """Set connection status."""
        self._connected = value
    
    def connect(self, address: str, device_name: str = "", timeout: float = 18) -> ConnectionResult:
        """Resolve each exact service on this peer; keep the legacy 6 Play path.

        Called by the controller's background connection worker. A disconnect
        cancels both SDP and a pending socket. No authentication is inferred.
        """
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
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
                        self._connected = True
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
                    return open_channel(uuid, channel, "windows_sdp")
                except ConnectionCancelled:
                    raise
                except OSError as exc:
                    last_error = exc
                    log.warning("RFCOMM stage=connection uuid=%s channel=%s source=windows_sdp error=%s", uuid, channel, exc)
            # Only when SDP could not resolve any service. Never label this FD2D.
            if not resolved and " ".join(device_name.split()).casefold() == "redmi buds 6 play":
                return open_channel(None, RFCOMM_PORT, "profile_fallback")
            budget(SOCKET_TIMEOUT)
            raise ConnectionError("No usable RFCOMM service for selected device") from last_error

    def disconnect(self) -> None:
        """Cancel pending work and close the current transport."""
        with self._state_lock:
            self._cancel.set()
            self._connected = False
            self.result = None
            sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def send(self, data: bytes) -> None:
        """Send data to device.
        
        Args:
            data: Bytes to send
            
        Raises:
            Exception: If send fails
        """
        with self._lock:
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
        if self._sock:
            data = self._sock.recv(RECV_BUFFER_SIZE)
            if not data:
                self.disconnect()
            return data
        return b""
