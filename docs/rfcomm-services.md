# RFCOMM service resolution

Windows uses native Winsock SDP; Linux reads the selected peer's BlueZ SDP records with `sdptool`. Both resolve the exact service UUID,
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

If SDP cannot resolve a usable service channel, the connection attempt fails,
including for Redmi Buds 6 Play.

Linux requires the BlueZ `sdptool` executable. Its `search` command does not
accept arbitrary 128-bit UUID strings. Bluetooth-base UUIDs are queried directly
with `search --bdaddr`, including services outside the public browse group.
For vendor UUIDs the app uses `browse --xml` on only the selected peer. It always
matches complete ServiceClassIDList/ServiceID UUIDs in the returned records.
The RFCOMM channel must belong to that same record's ProtocolDescriptorList
and be in 1–30. Standard short UUIDs are expanded with the Bluetooth base UUID;
the XiaoAI vendor UUID is never reduced to standard SPP. Ambiguous channels or
malformed records fail discovery. Each child process has a bounded timeout and
is killed and reaped on cancellation. No RFCOMM channel scanning occurs.
Successful Linux results record `resolution_source="linux_sdp"`; Windows keeps
`"windows_sdp"`. Authentication selection depends on service UUID, not platform.

## Validation

`tests/test_rfcomm_services.py` uses fake backends/processes to check per-peer
channels, UUID order, failed socket cleanup, unresolved services, cancellation,
the total budget, and query process termination. These are software tests,
not earbud validation. The native C# adapter can also be compiled on Windows
without querying a device. Actual SDP and command behavior must be checked
with Redmi Buds 6 Play hardware; no additional model is marked verified.

For hardware validation, connect the paired 6 Play, check the logged UUID,
channel and resolution source, then exercise battery, latency, gestures and EQ.
Test disconnect during SDP and retry. When SDP is unavailable, confirm that
the connection fails before opening a socket. Record hardware results separately from
fake backend results.

Native API reference:
[Microsoft Bluetooth service discovery](https://learn.microsoft.com/en-us/windows/win32/bluetooth/bluetooth-and-wsalookupservicebegin-for-service-discovery).
