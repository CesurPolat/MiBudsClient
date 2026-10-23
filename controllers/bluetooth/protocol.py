"""Protocol handling for Mi Buds communication."""

from dataclasses import dataclass
from typing import Optional

from .constants import (
    BATTERY_PATTERN,
    BATTERY_REQUEST_PAYLOAD,
    MODE_COMMAND_TEMPLATE,
    COUNTER_VALUE,
    PACKET_SIZE_MODE_ACK
)


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class BatteryStatus:
    """Battery levels for all components."""
    left: int
    right: int
    case: int


# ─────────────────────────────────────────────────────────────────────────────
# Protocol Handler
# ─────────────────────────────────────────────────────────────────────────────
class BudsProtocol:
    """Handles protocol encoding/decoding for Mi Buds."""
    
    @staticmethod
    def build_mode_command(mode: str) -> bytes:
        """Build latency mode command payload.
        
        Args:
            mode: "low" for low latency, anything else for standard
            
        Returns:
            Bytes payload to send
        """
        param = "01" if mode == "low" else "00"
        counter = hex(COUNTER_VALUE)[2:].zfill(2)
        payload = MODE_COMMAND_TEMPLATE.format(counter=counter, param=param)
        return bytes.fromhex(payload)
    
    @staticmethod
    def build_battery_request() -> bytes:
        """Build battery status request payload."""
        return bytes.fromhex(BATTERY_REQUEST_PAYLOAD)
    
    @staticmethod
    def parse_battery(data: bytes) -> Optional[BatteryStatus]:
        """Parse battery information from data packet.
        
        Args:
            data: Raw data received from device
            
        Returns:
            BatteryStatus if found, None otherwise
        """
        try:
            idx = data.find(BATTERY_PATTERN)
            if idx == -1 or len(data) < idx + 7:
                return None
            
            return BatteryStatus(
                left=data[idx + 4],
                right=data[idx + 5],
                case=data[idx + 6]
            )
        except Exception:
            return None
    
    @staticmethod
    def is_battery_packet(data: bytes) -> bool:
        """Check if packet contains battery status pattern."""
        return BATTERY_PATTERN in data
    
    @staticmethod
    def is_mode_ack_packet(packet_size: int) -> bool:
        """Check if packet size indicates a mode acknowledgment packet."""
        return packet_size == PACKET_SIZE_MODE_ACK
    
    @staticmethod
    def get_mode_name(mode: str) -> str:
        """Get human-readable mode name."""
        return "Low latency" if mode == "low" else "Standard"
