# RFCOMM service resolution

Windows resolves the selected peer's exact service UUID with native Winsock SDP,
in the APK's order: MIUI (`0000fd2d-0000-1000-8000-00805f9b34fb`),
XiaoAI (`00001101-0000-1000-8000-008584d01810`), then standard SPP
(`00001101-0000-1000-8000-00805f9b34fb`). No channel scanning is performed.

`PlatformBackend` runs the native query in a hidden PowerShell child, using
`WSALookupServiceBeginW` with `LUP_FLUSHCACHE` and `WSALookupServiceNextW`
with `LUP_RETURN_ADDR`. Returned endpoints must match the selected address,
RFCOMM protocol, and a channel in 1–30. This avoids relying on stale registry
SDP cache or installing a Bluetooth library. Each lookup has a four-second
budget, each socket connect at most two seconds, and the entire attempt at most
18 seconds. Timeouts/cancellation kill and reap the query child. Disconnect
closes a pending socket; connection work stays in existing background workers.

`BluetoothConnection.connect(address, device_name=...)` returns a
`ConnectionResult` containing the socket, service UUID, channel, and resolution
source. The controller exposes it as `connection_result`. The result is cleared
on disconnect. A transport connection is not authentication or protocol support.
The existing single reader, framing, and 6 Play command flow remain in place.
This change does not implement SAFER+ or enable additional model backends.

If no service channel could be resolved, only the exact normalized name
`Redmi Buds 6 Play` permits the existing channel 6 fallback. That result has
`service_uuid=None` and `resolution_source="profile_fallback"`. No service/auth
identity is inferred from that channel. If a service was resolved but its
connection failed, no speculative profile fallback is attempted. Linux keeps
the existing socket transport and 6 Play fallback; live Linux SDP is not added.
Callers providing only a MAC address must also supply the known device name to
qualify for fallback; an unknown peer never inherits channel 6.

## Validation

`tests/test_rfcomm_services.py` uses fake backends/processes to check per-peer
channels, UUID order, failed socket cleanup, profile restrictions, cancellation,
the total budget, and query process termination. These are software tests,
not earbud validation. The native C# adapter can also be compiled on Windows
without querying a device. Actual SDP and command behavior must be checked
with Redmi Buds 6 Play hardware; no additional model is marked verified.

For hardware validation, connect the paired 6 Play, check the logged UUID,
channel and resolution source, then exercise battery, latency, gestures and EQ.
Test disconnect during SDP and retry. When SDP is unavailable, confirm that
the result records the explicit unknown-UUID profile fallback and that the
existing direct commands still work. Record hardware results separately from
fake backend results.

Native API reference:
[Microsoft Bluetooth service discovery](https://learn.microsoft.com/en-us/windows/win32/bluetooth/bluetooth-and-wsalookupservicebegin-for-service-discovery).
