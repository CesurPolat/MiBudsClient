# Current ANC panel behavior

The connected device function list now controls ANC/transparency panel visibility.
Functions 1002, 1003, 1006, 1007 enable ANC; 1004, 1005 enable transparency.
No MIBUDS_EXPERIMENTAL_ANC flag or PowerShell launcher is needed for visibility.
The experimental UI notice has been removed. Device-confirmed reads and writes
remain unchanged. Function support does not certify hardware protocol compatibility;
existing model authentication policies still apply and are not inferred from functions.

The following notes describe the earlier opt-in validation workflow and are historical.

# ANC implementation status

The APK-derived implementation is disabled for all production models. An exact
model opt-in enables the experimental Flet controls for hardware testing only.
Catalog capabilities do not certify protocol compatibility.

## Run the test build (Windows)

Build using the repository's Flet environment, or use the locally validated EXE
in `.validation-pack/MiBudsClient.exe`. Close all existing instances first (the
single-instance feature otherwise reuses the instance without the test flags).

```powershell
.\tools\test-anc.ps1 -Model 'miwear.headphone.n76g' -Auth command_auth
# A separately built EXE can be supplied:
.\tools\test-anc.ps1 -Model 'miwear.headphone.n76g' -Auth command_auth -Executable 'C:\path\MiBudsClient.exe'
```

`n76g` is Redmi Buds 5 Pro; replace it with the exact catalog model ID only after
the tester reports their actual model. The script's default is a test candidate,
not a statement that the tester owns it. Do not enable direct auth automatically
after command auth fails. Testing direct mode requires explicitly launching again
with `-Auth direct`; record both runs separately.

The two independent opt-ins are `MIBUDS_EXPERIMENTAL_ANC=<exact catalog model ID>`
and `MIBUDS_EXPERIMENTAL_AUTH=command_auth|direct`. No model enters the production
allowlist. The existing 6 Play policy is unchanged, and the ANC card remains
hidden for its catalog (no ANC/transparency capabilities).

## Tester checklist (English / Spanish)

1. Report exact earbuds model, firmware version, Windows version, and selected
   auth policy. / Indica modelo exacto, firmware, Windows y política de auth.
2. Open Settings > Noise control > Read device settings. Verify the initial mode
   and level. / Lee los ajustes y verifica el modo y nivel actuales.
3. Choose Off, ANC, then Transparency (only the modes the model supports). Check
   the audible effect and the mode read back by the app after every change.
   / Prueba Desactivado, Cancelación y Transparencia; comprueba el efecto real
   y el estado confirmado en la aplicación.
4. Select supported levels and note whether the order matches the device.
   / Comprueba los niveles y su orden. Do not infer a dB value from the wire code.
5. Change mode using the earbuds' physical gesture. Check whether the UI updates;
   press Read if no F4 notification arrives. / Cambia el modo desde los audífonos
   y comprueba la actualización de la interfaz.
6. Disconnect/reconnect, and confirm no old result is shown for the new session.
   / Desconecta y reconecta; comprueba que no aparece un estado antiguo.

The launcher prints the local capture path (`%TEMP%/mibuds-anc-*.jsonl`). This is
opt-in local diagnostic data, not automatic telemetry. Share it manually after
review. It contains a session header plus timestamped post-auth TX/RX byte chunks;
chunks may contain partial or multiple frames. The SAFER+ handshake itself is
not captured here. Add the exact firmware and audible observations to the report.

Implemented: catalog base gear order, separate ANC/transparency capabilities,
adaptive route metadata, 08/type04 mode writes, F2/000B level writes, F3/000B
readback, F4 parsing, raw unknown state preservation, serialized transactions
and session-generation checks. ACK data is not interpreted as current state.
Extended FF CommonConfig records fail closed until their framing is implemented.

Pending before enabling a model:

- Record exact model, firmware, service UUID, channel and auth/session policy.
- Capture directed TX/RX for off, ANC and transparency where supported; verify
  audible behavior and F3 readback, including physical gesture changes.
- Validate level order on hardware, wearing rules and firmware-dependent gears.
- Add only that validated model to the backend allowlist.
- F4 callbacks, requested ACKs and Flet mode/level controls are implemented.
  ReportStatus-only changes still require the Read action if no F4 arrives.

Adaptive/smart/immersive writes and wear-state reads are not implemented.
The existing 6 Play packets, discovery and startup behavior remain unchanged.
New strings are authored in English, Turkish and Spanish; other locales use
explicit English fallback entries until translated. ACK success followed by a
different readback is an error, not a saved setting.

## Validation performed on 2026-11-01

- 305 unittest tests passed, including fragmented readback, wrong sequence,
  cancellation, stale UI results, opt-in gating and local capture behavior.
- Windows Flet/PyInstaller build completed successfully.
- Packaged EXE started and exited with code 0 through the existing-instance
  path while the user's current app stayed running. A fresh standalone GUI
  launch was not exercised; existing processes were not stopped.
- No ANC hardware validation was performed; production allowlist remains empty.
