# REDMI Buds 8 Pro

## Source version versus published executable

As checked on 2026-11-11, the newest upstream release is
[v0.2.0](https://github.com/CesurPolat/MiBudsClient/releases/tag/v0.2.0),
published on 2026-04-13. Its README lists only Redmi Buds 6 Play, and its
connection code uses a fixed RFCOMM channel. Downloading that EXE does not
provide the newer catalog, service discovery, authentication or settings UI.

Current source already includes the global Buds 8 Pro catalog record:
`miwear.headphone.p76gl`, VID `0x2717`, PID `0x50E5`, sale model `M2535E1`.
The SDK fallback also names PID `0x50E3`; it has no bundled app record of its
own, so this document does not assign the global variant's functions to it.
Recognition and successful authentication are separate from feature support.

## Available controls from the global catalog

| Control | Catalog options used by this client |
| --- | --- |
| Battery | Left, right and case values when reported by the device. |
| Noise control | Off, ANC and transparency; ANC gear codes 0–19 and transparency codes 0–2. These codes are not dB measurements. |
| EQ presets | Default (0), bass (5), treble (6), vocals (1). Custom (10) remains hidden. |
| Tap gestures | Single, double and triple tap, with the model's own allowed actions. |
| Long press | Unassigned (8), voice assistant (0), noise control (6). |
| Swipe | Volume control (11) or unassigned (8), independently for each earbud. |

This change adds swipe editing. Other rows describe existing source behavior,
not features newly implemented or hardware-verified by this contribution.
The swipe row appears only when config 0x0002 actually returns gesture type 5;
missing assignments are not invented. Changes preserve the other side with
0xFF, use the existing serialized transaction, and require matching readback
before being displayed as saved.

Low latency is not exposed because this record has no function 3011. Multipoint,
wear detection, spatial audio, smart/immersive ANC and other unimplemented
catalog functions remain metadata. This is not full feature parity with the
Xiaomi Earbuds app.

## Try the source version

Follow the [source installation instructions](../README.md#run-from-source)
using the branch containing this change. Close any previously installed EXE
with the tray's **Quit** command first: single-instance protection would
otherwise bring the old EXE back instead of starting the source version.
Pair and connect the earbuds in the operating system, then run `python main.py`
in the configured environment. No channel override or model opt-in is needed.
The existing service-based authentication remains unchanged; authentication
failures must not be bypassed with direct commands.

## Manual hardware report

Hardware checks remain for an owner to perform. Do not mark a model verified
from catalog metadata or synthetic packets alone.

1. Record the app commit, exact model/region, firmware version, OS, resolved
   service UUID/channel and the reported authentication result from F12.
2. Compare both earbud battery readings and the case reading when available.
3. In Settings > Gestures, load assignments and locate Swipe / Deslizar.
4. Enable Volume control on the left; check the right assignment is preserved,
   and physically swipe to check the audible volume change.
5. Repeat for the right earbud; try Unassigned and restore the preferred values.
6. Reopen settings and reconnect to check persistence. Note any rejection,
   timeout, missing gesture or mismatch instead of reporting it as a success.
7. Separately check ANC/transparency and EQ before claiming those existing
   paths work on this model. Check that reconnects do not show stale settings.

No hardware validation, automated tests or executable build was performed for
this change. The repository workflow leaves those activities to explicit user
requests.

## Protocol evidence

The bundled Xiaomi catalog supplies function 4011 and actions [11, 8] for the
global Buds 8 Pro record. The wire mapping is documented independently in
XiaomiTWS at commit `0927e57cae772ac1016691b0930fb279fff51229`:

- [Gesture types and functions](https://github.com/web1n/android_packages_apps_XiaomiTWS/blob/0927e57cae772ac1016691b0930fb279fff51229/src/org/lineageos/xiaomi_tws/mma/ConfigData.kt)
  defines Swipe as 0x05, VolumeControl as 0x0B and Disabled as 0x08.
- [Gesture codec](https://github.com/web1n/android_packages_apps_XiaomiTWS/blob/0927e57cae772ac1016691b0930fb279fff51229/src/org/lineageos/xiaomi_tws/mma/configs/Gesture.kt)
  uses config 0x0002, three-byte type/left/right groups and 0xFF for an unchanged
  side. This matches the client's existing assignment framing.

These are protocol references, not a packet capture from a Buds 8 Pro session.
