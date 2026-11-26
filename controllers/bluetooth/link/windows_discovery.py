"""Read connected Bluetooth Classic peers through the Windows Bluetooth API.

This only enumerates local OS state: no inquiry, pairing or control connection.
Loaded lazily by discovery.py so Linux never loads a Windows library.
"""
import ctypes
from ctypes import wintypes


class _SystemTime(ctypes.Structure):
    _fields_ = [
        ("year", ctypes.c_uint16), ("month", ctypes.c_uint16),
        ("day_of_week", ctypes.c_uint16), ("day", ctypes.c_uint16),
        ("hour", ctypes.c_uint16), ("minute", ctypes.c_uint16),
        ("second", ctypes.c_uint16), ("milliseconds", ctypes.c_uint16),
    ]


class _DeviceInfo(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("Address", ctypes.c_uint64),
        ("ulClassofDevice", wintypes.ULONG),
        ("fConnected", wintypes.BOOL),
        ("fRemembered", wintypes.BOOL),
        ("fAuthenticated", wintypes.BOOL),
        ("stLastSeen", _SystemTime),
        ("stLastUsed", _SystemTime),
        ("szName", wintypes.WCHAR * 248),
    ]


class _SearchParams(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("fReturnAuthenticated", wintypes.BOOL),
        ("fReturnRemembered", wintypes.BOOL),
        ("fReturnUnknown", wintypes.BOOL),
        ("fReturnConnected", wintypes.BOOL),
        ("fIssueInquiry", wintypes.BOOL),
        ("cTimeoutMultiplier", ctypes.c_ubyte),
        ("hRadio", wintypes.HANDLE),
    ]


def get_connected_devices() -> tuple[tuple[str, str], ...]:
    """Return (name, MAC) for connected Classic peers, never just paired ones."""
    api = ctypes.WinDLL("bthprops.cpl", use_last_error=True)
    first = api.BluetoothFindFirstDevice
    first.argtypes = [ctypes.POINTER(_SearchParams), ctypes.POINTER(_DeviceInfo)]
    first.restype = wintypes.HANDLE
    next_device = api.BluetoothFindNextDevice
    next_device.argtypes = [wintypes.HANDLE, ctypes.POINTER(_DeviceInfo)]
    next_device.restype = wintypes.BOOL
    close = api.BluetoothFindDeviceClose
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL

    params = _SearchParams()
    params.dwSize = ctypes.sizeof(params)
    params.fReturnConnected = True
    # All radios; no active inquiry and no remembered/disconnected devices.
    info = _DeviceInfo()
    info.dwSize = ctypes.sizeof(info)
    ctypes.set_last_error(0)
    handle = first(ctypes.byref(params), ctypes.byref(info))
    if not handle:
        error = ctypes.get_last_error()
        if error == 259:  # ERROR_NO_MORE_ITEMS: an empty result is not a failure.
            return ()
        if error:
            raise ctypes.WinError(error)
        raise OSError("BluetoothFindFirstDevice returned no enumeration handle")

    devices = []
    seen = set()
    try:
        while True:
            # Win32 BOOL values can be nonzero bit flags, not necessarily 1.
            if info.fConnected and info.Address:
                compact = f"{info.Address & 0xFFFFFFFFFFFF:012X}"
                address = ":".join(compact[i:i + 2] for i in range(0, 12, 2))
                if address not in seen:
                    devices.append((info.szName, address))
                    seen.add(address)
            info = _DeviceInfo()
            info.dwSize = ctypes.sizeof(info)
            ctypes.set_last_error(0)
            if not next_device(handle, ctypes.byref(info)):
                error = ctypes.get_last_error()
                if error == 259:
                    break
                if error:
                    raise ctypes.WinError(error)
                raise OSError("BluetoothFindNextDevice failed without an error code")
    finally:
        close(handle)
    return tuple(devices)
