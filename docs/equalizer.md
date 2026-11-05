# Equalizer

The home EQ controls read config `0007` on connection. The 20 explicitly
registered catalog models expose their own ordered profile buttons after a
successful device read. Models without an EQ catalog entry expose no buttons.
Config `0037` is queried only when the existing custom-band backend gate allows
it. Profile writes use config `0007` and require acknowledgment plus matching
readback. Custom profile ID 10 is currently excluded from every model's UI.

Multi-model selection is enabled at the user's request using the existing
codec. It has hardware validation only on Redmi Buds 6 Play. Connection service
discovery and authentication requirements still apply; catalog support alone
does not prove a model will accept the packets. Firmware-specific OTA lists
are not merged into the base list without firmware identification.

The custom profile button and band editor are currently hidden for every model,
even when the device reports active profile 10. The following
band-editing behavior describes the existing codec, not a newly enabled editor.

The local curve is a draft. Releasing a slider sends a preview, while Save
sends a separate persistence command. Reset requests the device's reset and
verifies a zero-gain curve. Writes require acknowledgment; presets, save and
reset also require matching readback. A failed operation keeps the draft
visible but requires closing and reopening the section before more writes.
Reopening replaces the draft
with device data. Disconnect clears the device state and invalidates pending
UI completions.

## Framing correction

The outer RCSP length includes both the sequence byte and the record-length
byte. For `N` bands, Save has record length `9 + 3*N` and outer length
`11 + 3*N`; Preview has record length `6 + 3*N` and outer length `8 + 3*N`.
Thus ten-band lengths are `27` / `00 29` for Save and `24` / `00 26` for
Preview. The earlier reference's outer lengths were one byte short. The
encoder calculates the outer length from actual bytes. Gains use sign
magnitude: 1000 Hz at −3 dB is `03 E8 83`.

## Hardware check — 2026-10-27

A connected Redmi Buds 6 Play was queried on RFCOMM 6:

* `0007` returned `01` (Vocal).
* `0037` returned `00`, which contains no custom-band data. The custom editor
  correctly stays unavailable; custom preview/save/reset remain unverified
  on hardware.
* Vocal → Balanced was acknowledged and read back as `00`.
* The original Vocal profile was restored and read back as `01`.

The custom codec and transactions have synthetic packet tests. These do not
establish custom EQ support on this device or compatibility with other models.
