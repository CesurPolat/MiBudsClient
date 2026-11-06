# Raw SPP authentication

`RawAuthSession` implements the alternative Xiaomi SPP handshake. AUTO selects it
only after connecting to the XiaoAI or standard SPP UUID. FD2D continues using
command auth; the existing unknown-UUID Redmi Buds 6 Play fallback stays direct.
Authentication errors close the socket, without changing UUID or bypassing auth.
No model allowlist or experimental opt-in is used.

## Wire exchange

These messages have no RCSP envelope, opcode, sequence or EF terminator.

| Direction | Message | Meaning |
|---|---|---|
| PC to earbuds | `00 + A[16]` | Fresh random challenge |
| Earbuds to PC | `01 + R(A)[16]` | Compare against expected answer |
| PC to earbuds | `02 70 61 73 73` | Earbuds authenticated |
| Earbuds to PC | `00 + B[16]` | Peer challenge |
| PC to earbuds | `01 + R(B)[16]` | Answer peer challenge |
| Earbuds to PC | `02 70 61 73 73` | Mutual authentication complete |

`R` is the existing `safer_plus.challenge_response`. Both challenges are exactly
16 bytes. The client uses `secrets.token_bytes` and a constant-time answer
comparison. The pass marker alone never authenticates a connection.

## Stream and lifecycle

The existing background connection worker remains the only socket reader until
auth finishes. The session consumes fixed-size raw messages from a receive
buffer, including fragmented and coalesced messages. Wrong types, answers,
result markers and stage order fail explicitly. Pre-auth RCSP traffic is not
silently treated as a successful session. After the final pass marker, all
remaining bytes, including partial RCSP frames, pass to the normal listener.

The initial challenge is sent after 0.5 seconds and retried twice, at 3-second
intervals, using the same challenge. A total 9.5-second deadline bounds the
exchange. These are nominal times; scheduling/socket IO can add latency.
Retries stop once the peer answers: unlike the APK timer, the Python client
does not restart the initial challenge in later stages. Each reconnect gets a
new challenge. Disconnect/abort clears the receive buffer, challenge, expected
answer and scheduling state. Normal commands remain gated until mutual success.

Logs show `Auth policy=raw_auth state=authenticating`, followed on success by
`Session policy=raw_auth ready=True authenticated=True`. Challenge/answer bytes
are not printed by this layer.

## Evidence and scope

The Java flow was recovered from Xiaomi Earbuds 1.37.1i
`BluetoothAuth.s/w/v`, the raw retry Runnable and the SPP service selection.

The native reference is
[libxm_bluetooth.so, ARM64](https://github.com/web1n/android_packages_apps_XiaomiTWS_xiaomi-sdk/blob/e5184dfefdbb9782cd0e0478cf1aa8e9350896ea/jniLibs/arm64-v8a/libxm_bluetooth.so):

- Size: 11,864 bytes.
- SHA-256: `7bc8974acebe61494751d692c5cd4aa91cf6623ad549689b40ea21c03a3b8691`.
- JNI raw entry `0x20cc`; command entry `0x2200`.
- Raw skips its leading 00 and prefixes its output with 01; both wrappers call
  `function_xiaomi` at `0x1b98`.
- That function computes E1, then E21 overwrites the entire output block.
  Using a standard JieLi E1 implementation alone would give the wrong result.

Offline research ran both real JNI wrappers with synthetic JNI/libc hooks in
Unicorn 2.1.4 ARM64 emulation. For 64 synthetic challenges, the native command
answer equalled the current Python answer, and the native raw answer equalled
`01 + Python answer` in every case. Examples (without the raw 01 prefix):

| Challenge | Answer |
|---|---|
| `00000000000000000000000000000000` | `bca5905bc849392e7bf9fdcdc570ef77` |
| `ffffffffffffffffffffffffffffffff` | `f26249f9a7bc42731feb945fd9e8d06f` |
| `000102030405060708090a0b0c0d0e0f` | `8713913c41434e091cad794a1b5d95c4` |

This library is a separately sourced reference, not the retained original
1.37.1i ARM split. These are native replay vectors, not earbud packet captures.
Raw hardware interoperability and a complete real session capture remain
unverified. No specific model has been established to require raw auth only.
Project test suites and builds were not run for this implementation change.
