# Command authentication

The optional `command_auth` policy implements mutual RCSP 0x50/0x51
authentication, separately from SDP, socket connection and model command codecs.
Implemented feature access is catalog-driven; no verified-device/model entry
is required. Runtime auth selection is independent of feature visibility.

## Current default policy

The controller defaults to `auto` for every model. After SDP/socket connection,
FD2D selects `command_auth`; XiaoAI/standard SPP select mutual `raw_auth`
(implemented separately in `raw_auth.py`; see [Raw authentication](raw-auth.md)). The existing 6 Play
unknown-UUID `profile_fallback` selects `direct`. This preserves its old path
without inferring a service from channel 6. An explicit developer API policy
override is still available; no environment opt-in is required.

## Earlier 6 Play hardware evidence (2026-10-31)

An actual connected Redmi Buds 6 Play was tested on Windows: live SDP resolved
FD2D to channel 6 and mutual command auth completed with `ready=True` and
`authenticated=True`. The test socket was then closed. Battery, EQ, gestures and
latency were not exercised in that authenticated session. Firmware identity and
a complete timestamped packet capture were not collected. This does not validate
additional models or establish equivalence with the APK native binary.

## Policy and use

`BTController(auth_policy="auto")` is the normal application path. Explicit
`command_auth`/`direct` policies remain developer APIs for diagnostics, not model
permission gates. `profile_auth_policy(name)` is a compatibility alias returning
AUTO; the name no longer selects authentication. Explicit `raw_auth` requires
a resolved XiaoAI or standard SPP service.

The low-level `BluetoothConnection.connect(..., session_policy=...)` API accepts
the same policies. Omitting policy on that low-level API preserves transport-only
operation for existing transport consumers; it does not report an authenticated
or ready protocol session. The app controller always supplies an explicit policy.

Command auth requires an SDP-resolved MIUI SPP UUID. AUTO selects it when the
connected service is FD2D; per-model validation or an extra opt-in is not required.
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
role/firmware interoperability; real disconnect and timeout behavior. Separate
offline research on 2026-11-06 established native equality for 64 inputs against
one identified ARM64 libxm_bluetooth reference binary, including the raw JNI
wrapper. See [Raw authentication](raw-auth.md) for its identity and limits;
this does not establish equality with every APK version or hardware support.
No model is promoted to verified by these checks.

