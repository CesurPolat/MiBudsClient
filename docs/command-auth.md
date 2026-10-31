# Command authentication

The optional `command_auth` policy implements mutual RCSP 0x50/0x51
authentication, separately from SDP, socket connection and model command codecs.
No new model backend or verified-device entry is enabled.

## 6 Play default policy (2026-10-31)

Redmi Buds 6 Play now defaults to `command_auth` after successful local hardware
verification and user confirmation. The temporary main.py test switch has been
removed. Other models remain `unknown`. An explicit `BTController(auth_policy="direct")`
override retains the legacy path for diagnostics; auth failure never enables it.

An actual connected Redmi Buds 6 Play was tested on Windows: live SDP resolved
FD2D to channel 6 and mutual command auth completed with `ready=True` and
`authenticated=True`. The test socket was then closed. Battery, EQ, gestures and
latency were not exercised in that authenticated session. Firmware identity and
a complete timestamped packet capture were not collected. This does not validate
additional models or establish equivalence with the APK native binary.

## Policy and use

`BTController(auth_policy="command_auth")` explicitly opts into experimental
command authentication for hardware validation. This is a developer API, not an
automatic model capability. The default profile resolver selects `command_auth` only
for the exact normalized Redmi Buds 6 Play name. Other names are `unknown` and
fail session establishment; they are not silently treated as direct or auth
devices. `raw_auth` is explicitly unsupported.

The low-level `BluetoothConnection.connect(..., session_policy=...)` API accepts
the same policies. Omitting policy on that low-level API preserves transport-only
operation for existing transport consumers; it does not report an authenticated
or ready protocol session. The app controller always supplies an explicit policy.

Command auth requires an SDP-resolved MIUI SPP UUID. An explicit opt-in plus this
service check permits the exchange; finding FD2D alone never enables auth.
XiaoAI, standard SPP and unknown-UUID channel 6 fallback cannot silently substitute
for this mode. A failed auth closes the selected socket and ends the attempt;
there is no direct/UUID fallback. A later controller retry starts a fresh socket
and session under the same policy.

6 Play's explicitly selected `direct` diagnostic path keeps the existing initialization/command bytes,
including its existing setup packet. `ready=True` in direct mode is never
reported as `authenticated=True`. The known channel 6 fallback remains available
for that model when SDP cannot resolve a service.

## Structure and lifecycle

- `auth_codec.py`: type role 4 for outbound frames/replies; accepts role 4 or 7;
  separates request sequence from response status + sequence.
- `safer_plus.py`: pure 16-byte challenge/answer calculation.
- `auth_session.py`: serialized state transitions, random per-session challenge,
  constant-time answer comparison, strict version/length/status checks,
  pending opcode + sequence matching and mutual completion.
- `connection.py`: bounded auth IO on the existing background connection worker,
  before publishing `connected`. It reads the socket only during this phase.
  The existing normal listener takes over afterward; concurrent public send/recv
  calls before publication are rejected. Complete normal frames and partial tails
  coalesced after the final auth result are preserved for the normal listener.

Our 0x51 ACK does not make the session ready. Only a valid peer 0x51 success
request after answering the peer's challenge does. Out-of-order peer requests
fail explicitly; no speculative reordering is implemented. Non-auth data before
READY is discarded, not replayed. Auth values are not written to diagnostic logs.

The local policy allows a 25-second total auth deadline, with 2-second 0x50 and
12-second 0x51 response deadlines and at most three response retries of the same
frame/sequence/challenge. The total deadline bounds both stages even after ACK.
The 25-second deadline and strict validation are our design choices, not claims
of exact APK parity. These budgets are additional to the transport's 18-second
budget. Disconnect closes the pending socket and clears parser, expected answer,
pending requests, prefetched data, ready/authenticated state. Reconnect uses a
fresh random challenge. Auth counters are session-local and configurable through
an injected sequence allocator; legacy normal command counters remain unchanged
and are used only after auth pending requests have been retired.

The controller exposes `transport_connected`, `session_ready`, and
`session_authenticated`. Connection logs distinguish transport opening from
session readiness/authentication.

## Source and license

The cipher is vendored from
[LeandroPG19/Buds](https://github.com/LeandroPG19/Buds/blob/e7e25b084114932ca962a61b35a37e5237702154/bluetooth/safer_plus.py),
commit `e7e25b084114932ca962a61b35a37e5237702154`. Its algorithm is unchanged;
local comments identify its provenance. The upstream module's references to
Gadgetbridge (AGPL-3.0) and XiaomayEarbudsWin (MIT) are preserved. The upstream
repository uses GPL v3, as does this project; see the repository's root `LICENSE`.
The duplicate license file under assets has been removed.
Do not relabel this Python source as MIT. The upstream hardware-validation claim
in its original docstring is not a hardware test performed by this project.

## Evidence and remaining hardware validation

`tests/test_command_auth.py` checks all five published Buds 5 Pro vectors,
table inversion, wrong sizes/answers, mutual completion, early ACK, wrong
sequence/target, malformed version/status, peer rejection, partial/coalesced
frames (including embedded EF), timeouts/retries, state reset, cancellation,
single-reader handoff, policy restrictions and the 6 Play direct fallback.
These are software/fake-peer tests, not hardware verification.

Still required: actual Redmi Buds 6 Play direct regression (battery, latency,
gestures and EQ); a complete direction/timestamped command-auth device capture;
native libxm_bluetooth equivalence; role/firmware interoperability; real disconnect
and timeout behavior. The current algorithm matches published vectors, not a
locally validated APK native binary. Raw auth needs separate native/capture
evidence and stream handling. No model is promoted to verified by these tests.

