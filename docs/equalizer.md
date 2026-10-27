# Equalizer

Settings → Equalizer reads config `0007` and `0037` separately. Presets come
from the exact Redmi Buds 6 Play catalog record. The custom editor requires a
valid version-1, EQ-ID-1 band response; missing or unsupported custom data does
not disable presets. No default ten-band curve is sent to the device.

The local curve is a draft. Releasing a slider sends a preview, while Save
sends a separate persistence command. Reset requests the device's reset and
verifies a zero-gain curve. Writes require acknowledgment; presets, save and
reset also require matching readback. A failed operation keeps the draft
visible but requires Refresh before more writes. Refresh replaces the draft
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
