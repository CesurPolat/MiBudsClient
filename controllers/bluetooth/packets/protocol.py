"""Protocol handling for Mi Buds communication."""

from dataclasses import dataclass
from typing import Optional

# Legacy battery values. Live queries use the target-info frame builder.
BATTERY_PATTERN = bytes.fromhex("02020407")
BATTERY_REQUEST_PAYLOAD = "fedcbac40200050bffffffffef"

MODE_COMMAND_TEMPLATE = "fedcbac4f20005{counter}03002f{param}ef"
COUNTER_VALUE = 0x90
PACKET_SIZE_MODE_ACK = 14


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
    def build_battery_request(counter=0x0B) -> bytes:
        """Build battery status request payload."""
        from .rcsp import build_identity_request
        return build_identity_request(counter)
    
    @staticmethod
    def parse_battery(data: bytes) -> Optional[BatteryStatus]:
        """Parse battery information from data packet.
        
        Args:
            data: Raw data received from device
            
        Returns:
            BatteryStatus if found, None otherwise
        """
        from ...battery.stream import BatteryStreamParser
        statuses = BatteryStreamParser().feed(data)
        return statuses[-1] if statuses else None
    
    @staticmethod
    def is_battery_packet(data: bytes) -> bool:
        """Check if packet contains battery status pattern."""
        return BudsProtocol.parse_battery(data) is not None
    
    @staticmethod
    def is_mode_ack_packet(packet_size: int) -> bool:
        """Check if packet size indicates a mode acknowledgment packet."""
        return packet_size == PACKET_SIZE_MODE_ACK
    
    @staticmethod
    def get_mode_name(mode: str) -> str:
        """Get human-readable mode name."""
        return "Low latency" if mode == "low" else "Standard"
