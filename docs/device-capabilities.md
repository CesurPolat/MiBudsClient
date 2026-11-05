# Device capabilities

`controllers/bluetooth/capabilities.py` separates APK UI function IDs from
Bluetooth configuration IDs. `FUNCTIONS` records the constants supplied by
`com.mi.earphone.device.manager.export.Function`; unspecified IDs such as 1001
remain raw metadata. No command is derived from a function number.

`resolve_capabilities(name, identity)` selects an exact full-name match among
the identity's VID/PID candidates, or a sole candidate. Without an identity it
uses the catalog name lookup. Ambiguous records are never merged. The result
retains all function metadata, including functions without an implementation.

`available` uses `MODEL_BACKENDS` for model-specific operations. EQ profile
selection is explicitly enabled by user request for the 20 `EQ_MODELS` with
base-catalog effects, using the existing RCSP config-7 read/write codec.
Only Redmi Buds 6 Play has hardware validation; availability on other models
is experimental and does not establish protocol compatibility. Remote catalog
updates cannot register additional model IDs. Battery support is a backend
capability because the catalog does not define a battery function ID.

`catalog_effects` retains the ordered IDs from 2016's `sound_effect.effects`
(or legacy 2006's `sound_effect` list). Selectable `profiles` retain only known
`PROFILE_KEYS`, including custom (10), from that exact model record. No other
model's list is merged in. The UI creates a button for each of those IDs after
a successful read; selecting one requires an acknowledgment and matching
readback. Unsupported IDs are rejected before transport. The buttons share the available
card width equally, without horizontal scrolling or profile tooltips.

Custom (10) selects a stored custom profile. The band editor remains hidden;
selecting this profile does not invent or upload a curve. Custom-band config
55 reads/writes retain their existing backend gate. Preset-only models read
only config 7.
Gesture choices come from `click_action`, restricted to actions implemented by
the current codec. Noise control is excluded from the current Play editor.

## Adding support

1. Identify the model's transport, read/write packets and response parser from
   protocol evidence. Keep function IDs separate from config IDs.
2. Implement its controller operations and Flet component. Register the
   component under `SettingsCard.device_components` and its function requirements
   under `COMPONENT_REGISTRY`. Metadata alone must not create a working control.
3. Test reads, writes, readback, errors and reconnection on the actual model.
   Record the model/firmware and evidence before enabling `MODEL_BACKENDS`.
4. Add model-specific tests proving unsupported operations cannot send packets.

Capabilities refresh through connection messages and catalog synchronization,
independently of image changes. Panels reset their operation tokens when
capabilities change, rejecting old completions. Disconnect resets their state;
latency device changes also clear the previous effective mode and hold.

ANC, transparency, spatial audio, multipoint, firmware updates and the other
catalog functions have metadata entries, but remain hidden until their model's
backend and component are implemented and verified. No new hardware support is
claimed by the initial capability infrastructure.

The bundled catalog contains the base lists. Xiaomi Buds 5 firmware 3.0.7.6
replaces default (0) with Harman (14), and Redmi Buds 6 firmware 1.1.5.1 adds
custom EQ (10), according to OTA records. Firmware is not currently resolved
for EQ, so these OTA lists are not applied or combined with the base lists.
Xiaomi Buds 4 Pro's base record mentions firmware 2.5.6.4. IDs 2, 3, 4, 16,
17 and 18 are known APK definitions but occur in none of these 25 base lists.
