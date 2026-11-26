"""Bluetooth controller and its public imports."""

import sys as _sys

from .auth import auth_codec, auth_session, raw_auth, safer_plus
from .debug import diagnostics
from .link import connection, discovery, sdp, windows_discovery
from .link.discovery import BluetoothDiscovery, BluetoothDevice
from .packets import config_transport, protocol, rcsp
from .packets.protocol import BudsProtocol
from .packets.rcsp import DeviceIdentity

# Preserve flat import paths with the same module instances as the subpackages.
for _module in (
    auth_codec, auth_session, raw_auth, safer_plus,
    diagnostics,
    connection, discovery, sdp, windows_discovery,
    config_transport, protocol, rcsp,
):
    _name = _module.__name__.rsplit(".", 1)[-1]
    _sys.modules[f"{__name__}.{_name}"] = _module
del _module, _name


def __getattr__(name):
    if name == "BTController":
        # Feature transports can import the shared Bluetooth modules directly.
        from .controller import BTController

        return BTController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
