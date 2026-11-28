"""Classify link failures and forward their diagnostic context."""

import errno
import socket
import traceback

from utils.app.i18n import message as m
from utils.diagnostics.error_reports import redact

from ...catalog.capabilities import resolve_capabilities
from ...catalog.device_catalog import catalog_diagnostics
from ..auth.auth_session import AuthError


def connection_failure_reason(error, stage):
    """Classify wrapped SDP/socket errors using their original causes."""
    causes, visited = [], set()
    while error is not None and id(error) not in visited and len(causes) < 8:
        visited.add(id(error))
        causes.append(error)
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    if any(isinstance(cause, AuthError) for cause in causes):
        return m("connection.auth_failed")
    if any(isinstance(cause, PermissionError)
           or getattr(cause, "errno", None) in (errno.EACCES, errno.EPERM, 10013)
           or getattr(cause, "winerror", None) in (5, 10013) for cause in causes):
        return m("connection.permission")
    if any(isinstance(cause, (TimeoutError, socket.timeout))
           or getattr(cause, "errno", None) in (errno.ETIMEDOUT, 10060)
           or getattr(cause, "winerror", None) == 10060 for cause in causes):
        return m("connection.timeout")
    return m("connection.service_failed" if stage == "resolution" else "connection.establish_failed")


def report_connection_error(error, action, *, connection, device_name, device_check,
                            discovered_devices, identity, on_error):
    error.bluetooth_diagnostics = {
        "device": device_name,
        "device_check": device_check,
        "discovered_devices": discovered_devices,
        "stage": "receive" if action == "bluetooth_receive" else connection.stage,
        "transport": list(connection.diagnostics),
        "authentication": connection.auth_diagnostics,
        "identity": identity,
        "catalog": catalog_diagnostics(),
        "catalog_match": {"model": resolve_capabilities(device_name).model,
                          "source": "bluetooth_name", "device_identity_verified": False},
    }
    print(f"[Bluetooth] Error report device identity: {redact(identity)}")
    print(redact("".join(traceback.format_exception(type(error), error, error.__traceback__))))
    if on_error:
        try:
            on_error(error, action)
        except Exception as exc:
            print(f"[Bluetooth] Could not prepare error report: {redact(exc)}")
