# Device capabilities

`controllers/bluetooth/capabilities.py` separates APK UI function IDs from
Bluetooth configuration IDs. `FUNCTIONS` records the constants supplied by
`com.mi.earphone.device.manager.export.Function`; unspecified IDs such as 1001
remain raw metadata. No command is derived from a function number.

`resolve_capabilities(name, identity)` selects an exact full-name match among
the identity's VID/PID candidates, or a sole candidate. Without an identity it
uses the catalog name lookup. Ambiguous records are never merged. The result
retains all function metadata, including functions without an implementation.

`available` follows the selected model's `func_list` through `COMPONENT_REGISTRY`.
There are no model-validation/backend allowlists or experimental activation flags.
Implemented controls: EQ presets (2006/2016), touch gestures (4001/4002/4003/4006/4011),
manual low latency (3011), ANC (1002/1003/1006/1007), and transparency (1004/1005).
Only that device's own profile/gesture/level options can be selected. A new model
with these functions needs no source-code registration. Battery is basic telemetry
for recognized catalog devices, since it has no separate function ID.
Catalog access is not a claim that every device was hardware-tested; protocol
rejections and timeouts remain runtime errors rather than activation gates.

`catalog_effects` retains the ordered IDs from 2016's `sound_effect.effects`
(or legacy 2006's `sound_effect` list). Selectable `profiles` retain only known
`PROFILE_KEYS`, excluding hidden custom (10), from that exact model record. No other
model's list is merged in. The UI creates a button for each of those IDs after
a successful read; selecting one requires an acknowledgment and matching
readback. Unsupported IDs are rejected before transport. The buttons share the available
card width equally, without horizontal scrolling or profile tooltips.

Custom (10) remains in raw catalog metadata but is hidden on every model,
including when it is the device's active profile. It is excluded from selectable
profiles and controller profile writes. The band editor defaults to hidden too.
Existing custom-band codec support is retained for future work.
Gesture choices come from `click_action`, restricted to actions represented by
the current codec, including noise control when present in that model's list.
`GESTURE_FUNCTION_TYPES` maps catalog function 4011 to config 0x0002's swipe
type 0x05. It shares the existing per-earbud assignment, ACK and readback flow;
4011 is never used as a Bluetooth configuration ID. The UI only shows swipe
when both the model's catalog and the device's returned assignments include it.
See [REDMI Buds 8 Pro](redmi-buds-8-pro.md) for catalog scope and protocol sources.

## Adding support

1. For an already implemented feature, update catalog metadata; do not add a
   model allowlist or require hardware certification to unlock controls.
2. For a new feature, identify its actual protocol and implement controller/UI
   operations. Register feature IDs under `COMPONENT_REGISTRY`; do not turn an
   unknown function ID directly into an RFCOMM config ID.
3. Preserve model-specific interpretation exceptions (for example L71 level
   labels). They must not become model permission lists.
4. Leave hardware testing to the user. Add/run tests or build only on request.

Capabilities refresh through connection messages and catalog synchronization,
independently of image changes. Panels reset their operation tokens when
capabilities change, rejecting old completions. Disconnect resets their state;
latency device changes also clear the previous effective mode and hold.

ANC/transparency controls are enabled by their function IDs. Unimplemented
features such as spatial audio, multipoint and firmware updates remain metadata;
their mere presence does not create a control without a codec/UI implementation.
Custom EQ is explicitly deferred and never granted, even when effects has 10.

Auth uses the connected service, not a model name: AUTO selects command auth
for FD2D. XiaoAI/standard SPP select mutual raw auth (see `raw-auth.md`).
The existing unknown-UUID 6 Play fallback retains its direct
path. An auth failure never silently switches to direct or another UUID.

The bundled catalog contains the base lists. Xiaomi Buds 5 firmware 3.0.7.6
replaces default (0) with Harman (14), and Redmi Buds 6 firmware 1.1.5.1 adds
custom EQ (10), according to OTA records. Firmware is not currently resolved
for EQ, so these OTA lists are not applied or combined with the base lists.
Xiaomi Buds 4 Pro's base record mentions firmware 2.5.6.4. IDs 2, 3, 4, 16,
17 and 18 are known APK definitions but occur in none of these 25 base lists.
