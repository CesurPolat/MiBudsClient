"""Main Bluetooth Controller for Mi Buds."""

import socket
import time
from typing import Callable, Optional

from .connection import BluetoothConnection
from .discovery import BluetoothDiscovery
from .protocol import BudsProtocol
from .constants import RECONNECT_DELAY


# ─────────────────────────────────────────────────────────────────────────────
# Type Aliases
# ─────────────────────────────────────────────────────────────────────────────
StatusCallback = Callable[[str, str], None]
BatteryCallback = Callable[[int, int, int], None]
CheckBatteryCallback = Callable[[], None]


# ─────────────────────────────────────────────────────────────────────────────
# Controller
# ─────────────────────────────────────────────────────────────────────────────
class BTController:
    """High-level controller for Mi Buds communication."""
    
    def __init__(
        self,
        status_callback: Optional[StatusCallback] = None,
        battery_callback: Optional[BatteryCallback] = None,
        check_battery_callback: Optional[CheckBatteryCallback] = None,
        bd_addr: Optional[str] = None
    ):
        self._connection = BluetoothConnection()
        self._protocol = BudsProtocol()
        self._bd_addr = bd_addr
        self._running = True
        
        # Callbacks
        self._status_callback = status_callback
        self._battery_callback = battery_callback
        self._check_battery_callback = check_battery_callback
    
    # ─────────────────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────────────────
    @property
    def connected(self) -> bool:
        """Check if connected to device."""
        return self._connection.connected
    
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
    
    # ─────────────────────────────────────────────────────────────────────────
    # Connection
    # ─────────────────────────────────────────────────────────────────────────
    def connect(self) -> bool:
        """Connect to the Mi Buds device."""
        # Discover device if address not set
        if not self._bd_addr:
            device = BluetoothDiscovery.get_connected_device()
            if not device or not device.address:
                self._update_status("No connected Bluetooth device found", "red")
                return False
            self._bd_addr = device.address
            self._update_status(f"MAC found: {self._bd_addr}", "blue")
        
        # Establish connection
        try:
            self._connection.connect(self._bd_addr)
            self._update_status("Connected", "blue")
            self.on_connect_setup()
            return True
        except Exception as e:
            self._connection.connected = False
            self._update_status(f"Connection failed: {e}", "red")
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
            return False, "Could not connect to device."
        
        try:
            payload = self._protocol.build_mode_command(mode)
            self._connection.send(payload)
            mode_name = self._protocol.get_mode_name(mode)
            return True, f"{mode_name} mode sent."
        except Exception as e:
            self._connection.connected = False
            return False, f"Send error: {e}"
    
    def request_battery(self) -> tuple[bool, str]:
        """Request battery status from device."""
        if not self._ensure_connected():
            return False, "Could not connect to device."
        
        try:
            payload = self._protocol.build_battery_request()
            self._connection.send(payload)
            return True, "Battery request sent."
        except Exception as e:
            self._connection.connected = False
            return False, f"Request error: {e}"
    
    def send_raw(self, data: bytes) -> tuple[bool, str]:
        """Send raw bytes to device.
        
        Args:
            data: Raw bytes to send
            
        Returns:
            (success, message) tuple
        """
        if not self._ensure_connected():
            return False, "Could not connect to device."
        
        try:
            self._connection.send(data)
            return True, f"Raw data sent: {data.hex()}"
        except Exception as e:
            self._connection.connected = False
            return False, f"Send error: {e}"
    
    def _ensure_connected(self) -> bool:
        """Ensure connected, attempting to connect if not."""
        return self._connection.connected or self.connect()
    
    def on_connect_setup(self):
            """Send a sequence of packets on connection."""
            packets = [
                "fedcbac40200050bffffffffef4f",
                "fedcbac4500012000167c6697351ff4aec29cdbaabf2fbe346ef",
                "fedcba04500013000201111430f0d8777a5f68bace0ed764cd10",
                "fedcba04510003000301ef",
                "fedcbac4f2000804060028699265b9"
            ]
            for packet_hex in packets:
                test_bytes = bytes.fromhex(packet_hex)
                print(self.send_raw(test_bytes))
                time.sleep(0.1)
            # Also request battery after sending packets
            time.sleep(1)
            self.request_battery()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Listener
    # ─────────────────────────────────────────────────────────────────────────
    def listen(self) -> None:
        """Main listener loop for incoming data."""
        last_packet_size = 0
        
        while self._running:
            if not self._connection.connected:
                self.connect()
                time.sleep(RECONNECT_DELAY)
                continue
            
            try:
                last_packet_size = self._process_data(last_packet_size)
            except socket.timeout:
                continue
            except Exception:
                self._handle_disconnect()
    
    def _process_data(self, last_packet_size: int) -> int:
        """Process incoming data packet."""
        data = self._connection.receive()
        packet_size = len(data)
        print(f"Received data size: {packet_size}")

        # Check for battery data
        if self._protocol.is_battery_packet(packet_size):
            status = self._protocol.parse_battery(data)
            if status:
                self._notify_battery(status.left, status.right, status.case)
        
        # Check for mode acknowledgment
        elif self._protocol.is_mode_ack_packet(packet_size):
            if last_packet_size != packet_size:
                self._trigger_battery_check()
        
        return packet_size
    
    def _handle_disconnect(self) -> None:
        """Handle connection loss."""
        self._connection.connected = False
        self._update_status("Connection lost", "red")
        time.sleep(2)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Cleanup
    # ─────────────────────────────────────────────────────────────────────────
    def stop(self) -> None:
        """Stop the controller."""
        self._running = False
        self._connection.disconnect()
