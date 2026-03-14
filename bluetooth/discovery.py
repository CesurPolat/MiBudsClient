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
$bt = Get-PnpDevice -Class Bluetooth | Where-Object { $_.Status -eq 'OK' }
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
        return sys.platform in ["win32", "linux"]
    
    @classmethod
    def get_connected_device(cls) -> Optional[BluetoothDevice]:
        """Get the first connected Bluetooth device.
        
        Returns:
            BluetoothDevice if found, None otherwise
        """
        if not cls.is_supported():
            return None
        
        try:
            if sys.platform == "win32":
                output = cls._run_discovery_script_win()
                return cls._parse_output_win(output)
            elif sys.platform == "linux":
                return cls._get_connected_device_linux()
        except Exception:
            return None
        return None
    
    @staticmethod
    def _run_discovery_script_win() -> str:
        """Execute PowerShell discovery script."""
        # This flag prevents a console window from appearing on Windows.
        creation_flags = 0x08000000  # subprocess.CREATE_NO_WINDOW
        
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", POWERSHELL_DISCOVERY_SCRIPT],
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5,
            creationflags=creation_flags
        ).strip()
    
    @classmethod
    def _parse_output_win(cls, output: str) -> Optional[BluetoothDevice]:
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

    @classmethod
    def _get_connected_device_linux(cls) -> Optional[BluetoothDevice]:
        """Get connected Bluetooth device using bluetoothctl on Linux."""
        try:
            # Get list of devices
            devices_output = subprocess.check_output(["bluetoothctl", "devices"], text=True)
            for line in devices_output.splitlines():
                # Format: Device XX:XX:XX:XX:XX:XX Name
                parts = line.split(" ", 2)
                if len(parts) >= 3:
                    mac = parts[1]
                    name = parts[2]
                    
                    # Verify if connected
                    info_output = subprocess.check_output(["bluetoothctl", "info", mac], text=True)
                    if "Connected: yes" in info_output:
                        return BluetoothDevice(name=name, address=cls._format_mac(mac))
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return None
    
    @staticmethod
    def _format_mac(addr: str) -> str:
        """Format MAC address to standard format (XX:XX:XX:XX:XX:XX)."""
        if not addr:
            return addr
        cleaned = addr.replace(":", "").replace("-", "").replace(" ", "").upper()
        if len(cleaned) == 12:
            return ":".join(cleaned[i:i+2] for i in range(0, 12, 2))
        return addr
