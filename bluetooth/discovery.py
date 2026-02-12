"""Bluetooth device discovery (Windows only)."""

import subprocess
import json
import sys
from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class BluetoothDevice:
    """Represents a connected Bluetooth device."""
    name: str
    address: str


# ─────────────────────────────────────────────────────────────────────────────
# Discovery Script
# ─────────────────────────────────────────────────────────────────────────────
POWERSHELL_DISCOVERY_SCRIPT = r"""
$bt = Get-PnpDevice -Class Bluetooth -Status OK
$results = foreach ($d in $bt) {
    $isConn = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Device_IsConnected' -ErrorAction SilentlyContinue).Data
    if ($isConn -eq $true) {
        $addr = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Bluetooth_DeviceAddress' -ErrorAction SilentlyContinue).Data
        if ($addr -is [byte[]]) {
            $addrStr = ($addr | ForEach-Object { $_.ToString('X2') }) -join ':'
        } else {
            $addrStr = [string]$addr
        }
        [pscustomobject]@{ Name=$d.FriendlyName; Address=$addrStr }
    }
}
if ($results) { $results | ConvertTo-Json -Compress }
"""


# ─────────────────────────────────────────────────────────────────────────────
# Discovery Class
# ─────────────────────────────────────────────────────────────────────────────
class BluetoothDiscovery:
    """Handles Bluetooth device discovery."""
    
    @staticmethod
    def is_supported() -> bool:
        """Check if discovery is supported on current platform."""
        return sys.platform == "win32"
    
    @classmethod
    def get_connected_device(cls) -> Optional[BluetoothDevice]:
        """Get the first connected Bluetooth device.
        
        Returns:
            BluetoothDevice if found, None otherwise
        """
        if not cls.is_supported():
            return None
        
        try:
            output = cls._run_discovery_script()
            return cls._parse_output(output)
        except Exception:
            return None
    
    @staticmethod
    def _run_discovery_script() -> str:
        """Execute PowerShell discovery script."""
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", POWERSHELL_DISCOVERY_SCRIPT],
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5
        ).strip()
    
    @classmethod
    def _parse_output(cls, output: str) -> Optional[BluetoothDevice]:
        """Parse PowerShell JSON output to BluetoothDevice."""
        if not output:
            return None
        
        data = json.loads(output)
        
        if isinstance(data, list):
            for item in data:
                address = item.get("Address")
                if address:
                    return BluetoothDevice(
                        name=item.get("Name", ""),
                        address=cls._format_mac(address)
                    )
            return None
        
        return BluetoothDevice(
            name=data.get("Name", ""),
            address=cls._format_mac(data.get("Address", ""))
        )
    
    @staticmethod
    def _format_mac(addr: str) -> str:
        """Format MAC address to standard format (XX:XX:XX:XX:XX:XX)."""
        if not addr:
            return addr
        cleaned = addr.replace(":", "").replace("-", "").replace(" ", "").upper()
        if len(cleaned) == 12:
            return ":".join(cleaned[i:i+2] for i in range(0, 12, 2))
        return addr
