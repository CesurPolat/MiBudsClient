# AGENTS.md

## Must-follow constraints

- **Windows and Linux support.** Bluetooth discovery can use platform-specific implementations (Windows: PowerShell via `subprocess` + `Get-PnpDevice`, Linux: native Linux-compatible discovery). Keep behavior consistent across supported platforms.
- **Model-specific support.** Catalog features describe UI capabilities, not protocol compatibility. Existing codecs remain limited to Redmi Buds 6 Play. Enable additional model backends only after model-specific protocol and actual hardware validation.
- **Dynamic RFCOMM service discovery.** Resolve the selected device's RFCOMM channel by exact service UUID. `RFCOMM_PORT = 6` in `controllers/bluetooth/constants.py` is only a Redmi Buds 6 Play fallback when no service channel is resolved; record `service_uuid=None` and `resolution_source="profile_fallback"`. Do not infer service/auth from a channel or scan channels blindly.
- **Assets directory bundling.** Build uses `datas=[('assets', 'assets')]` in PyInstaller spec. All UI assets (icon.ico, images) must stay in `assets/` folder.
- **Single instance enforcement.** Application forbids multiple running instances via port 65432. Do not remove or change `check_for_existing_instance()` at app startup.
- **Flet-only UI.** The entire UI layer (including system tray via pystray) depends on Flet. Do not introduce other UI frameworks.

## Validation before finishing

- **Test with actual device.** Any changes to `controllers/bluetooth/protocol.py` or `controllers/bluetooth/constants.py` must be tested against Redmi Buds 6 Play hardware; unit tests alone are insufficient.
- **Build succeeds.** Run `flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"` and verify executable runs.
- **Single instance works.** Launch executable twice; second instance should exit silently and focus existing window.

## Repo-specific conventions

- **Protocol payloads are hex strings.** All Bluetooth command/response data in `controllers/bluetooth/constants.py` and `protocol.py` use `.fromhex()` conversion. Maintain consistency.
- **Battery encoding.** Raw byte values >= 128 indicate charging (subtract 128 for actual %). See `BatteryIndicator._format_battery()` in `ui/components.py`.
- **Callbacks over events.** BT controller uses callback functions (`status_callback`, `battery_callback`) instead of events. Maintain this pattern.
- **Resource paths via `get_resource_path()`** in `utils/resource_manager.py`. Use this for assets in UI code.
- **Version string format.** Semantic versioning with optional pre-release tags: `v1.2.3`, `v1.2.3-alpha.1`, `v1.2.3-beta.2`, `v1.2.3-rc1`. Parser in `utils/updater.py` supports these formats.

## Important locations

- **Device protocol details:** `controllers/bluetooth/constants.py` (BATTERY_PATTERN, MODE_COMMAND_TEMPLATE, timeouts)
- **Build config:** `MiBudsClient.spec` (assets bundling, icon path)
- **UI constants (colors, sizes):** `ui/constants.py`

## Change safety rules

- **Preserve backward compatibility.** Do not change protocol packets or device matching logic without testing on hardware.
- **Do not add external Bluetooth libraries.** Current implementation uses Python's `socket` module directly for RFCOMM. Keep it minimal.
- **GitHub URL is contractual.** Hardcoded in UI constants and used by updater. Changes break update checking and links.
