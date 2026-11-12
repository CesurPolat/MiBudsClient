"""Discover connected catalog models on Windows and Linux."""

import subprocess
import json
import sys
from dataclasses import dataclass
from typing import Optional

from .device_catalog import get_device_models_by_name


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
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$ErrorActionPreference = 'Stop'
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
    def _is_supported_device(name: str) -> bool:
        return bool(get_device_models_by_name(name))
    
    @staticmethod
    def is_supported() -> bool:
        """Check if discovery is supported on current platform."""
        return sys.platform in ["win32", "linux"]
    
    @classmethod
    def get_connected_device(cls) -> Optional[BluetoothDevice]:
        """Get the first connected device whose name is in the active catalog.
        
        Returns:
            BluetoothDevice if found, None otherwise
        """
        if not cls.is_supported():
            return None
        
        try:
            if sys.platform == "win32":
                return cls._get_connected_device_windows()
            elif sys.platform == "linux":
                return cls._get_connected_device_linux()
        except Exception as exc:
            print(f"[Bluetooth] Device discovery failed: {type(exc).__name__}: {exc}")
            return None
        return None
    
    @classmethod
    def _get_connected_device_windows(cls) -> Optional[BluetoothDevice]:
        """Prefer native connection state; retain the older PnP fallback."""
        try:
            from .windows_discovery import get_connected_devices
            devices = get_connected_devices()
            for name, address in devices:
                if address and cls._is_supported_device(name):
                    print(f"[Bluetooth] Windows native discovery selected {name!r}")
                    return BluetoothDevice(name=name, address=address)
            names = ", ".join(repr(name) for name, _ in devices)
            print(f"[Bluetooth] Windows native discovery: {len(devices)} connected "
                  f"Classic device(s), no catalog match" + (f": {names}" if names else ""))
        except OSError as exc:
            print(f"[Bluetooth] Windows native discovery failed: {exc}")

        # Preserve the existing Windows route for drivers that do not expose
        # their connected peer through BluetoothFindFirstDevice.
        try:
            device = cls._parse_output_win(cls._run_discovery_script_win())
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            detail = getattr(exc, "stderr", None)
            detail = detail.strip() if detail else str(exc)
            print(f"[Bluetooth] Windows PnP discovery failed: {type(exc).__name__}: {detail}")
            return None
        if device is not None:
            print(f"[Bluetooth] Windows PnP discovery selected {device.name!r}")
        return device

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
            stderr=subprocess.PIPE,
            creationflags=creation_flags
        ).strip()
    
    @classmethod
    def _parse_output_win(cls, output: str) -> Optional[BluetoothDevice]:
        """Parse PowerShell JSON output to BluetoothDevice."""
        if not output:
            return None
        
        data = json.loads(output)
        
        for item in data if isinstance(data, list) else [data]:
            if not isinstance(item, dict):
                continue
            address = item.get("Address")
            name = item.get("Name", "")
            if address and cls._is_supported_device(name):
                return BluetoothDevice(name=name, address=cls._format_mac(address))
        return None

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
                    if not cls._is_supported_device(name):
                        continue
                    
                    # Verify if connected
                    info_output = subprocess.check_output(["bluetoothctl", "info", mac], text=True, timeout=5)
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
