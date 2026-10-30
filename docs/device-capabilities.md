# Device capabilities

`controllers/bluetooth/capabilities.py` separates APK UI function IDs from
Bluetooth configuration IDs. `FUNCTIONS` records the constants supplied by
`com.mi.earphone.device.manager.export.Function`; unspecified IDs such as 1001
remain raw metadata. No command is derived from a function number.

`resolve_capabilities(name, identity)` selects an exact full-name match among
the identity's VID/PID candidates, or a sole candidate. Without an identity it
uses the catalog name lookup. Ambiguous records are never merged. The result
retains all function metadata, including functions without an implementation.

`available` is the intersection of catalog capabilities and `MODEL_BACKENDS`.
Only the existing Redmi Buds 6 Play backend is enabled. Remote catalog updates
cannot register a backend. Battery support is a backend capability because the
catalog does not define a battery function ID.

EQ presets come from 2016's `sound_effect.effects`; custom EQ additionally
requires effect 10. A presets-only read never requests custom config 55.
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
