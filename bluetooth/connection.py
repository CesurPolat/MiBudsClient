"""Bluetooth socket connection handler."""

import socket
import threading
from typing import Optional

from .constants import RFCOMM_PORT, SOCKET_TIMEOUT, RECV_BUFFER_SIZE


class BluetoothConnection:
    """Manages Bluetooth socket connection."""
    
    def __init__(self):
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._connected = False
    
    @property
    def connected(self) -> bool:
        """Check if currently connected."""
        return self._connected
    
    @connected.setter
    def connected(self, value: bool) -> None:
        """Set connection status."""
        self._connected = value
    
    def connect(self, address: str) -> None:
        """Establish connection to device.
        
        Args:
            address: Bluetooth MAC address
            
        Raises:
            Exception: If connection fails
        """
        self._sock = socket.socket(
            socket.AF_BLUETOOTH,
            socket.SOCK_STREAM,
            socket.BTPROTO_RFCOMM
        )
        self._sock.settimeout(SOCKET_TIMEOUT)
        self._sock.connect((address, RFCOMM_PORT))
        self._connected = True
    
    def disconnect(self) -> None:
        """Close the connection."""
        self._connected = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
    
    def send(self, data: bytes) -> None:
        """Send data to device.
        
        Args:
            data: Bytes to send
            
        Raises:
            Exception: If send fails
        """
        with self._lock:
            if self._sock:
                self._sock.send(data)
    
    def receive(self) -> bytes:
        """Receive data from device.
        
        Returns:
            Received bytes
            
        Raises:
            socket.timeout: If no data available
            Exception: If receive fails
        """
        if self._sock:
            return self._sock.recv(RECV_BUFFER_SIZE)
        return b""
