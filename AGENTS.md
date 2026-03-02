# AGENTS.md

## Must-follow constraints

- **Windows only.** Bluetooth discovery via PowerShell (`subprocess`, `Get-PnpDevice`) is Windows-specific. Do not add cross-platform compatibility.
- **Redmi Buds 6 Play only.** Supported device is hardcoded. Protocol parsing (battery pattern, mode commands) is device-specific; changes require testing on actual hardware.
- **Single RFCOMM port.** RFCOMM_PORT = 6 in `bluetooth/constants.py`. Do not make this configurable.
- **Assets directory bundling.** Build uses `datas=[('assets', 'assets')]` in PyInstaller spec. All UI assets (icon.ico, images) must stay in `assets/` folder.
- **Single instance enforcement.** Application forbids multiple running instances via port 65432. Do not remove or change `check_for_existing_instance()` at app startup.
- **Flet-only UI.** The entire UI layer (including system tray via pystray) depends on Flet. Do not introduce other UI frameworks.

## Validation before finishing

- **Test with actual device.** Any changes to `bluetooth/protocol.py` or `bluetooth/constants.py` must be tested against Redmi Buds 6 Play hardware; unit tests alone are insufficient.
- **Build succeeds.** Run `flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"` and verify executable runs.
- **Single instance works.** Launch executable twice; second instance should exit silently and focus existing window.

## Repo-specific conventions

- **Protocol payloads are hex strings.** All Bluetooth command/response data in `bluetooth/constants.py` and `protocol.py` use `.fromhex()` conversion. Maintain consistency.
- **Battery encoding.** Raw byte values >= 128 indicate charging (subtract 128 for actual %). See `BatteryIndicator._format_battery()` in `ui/components.py`.
- **Callbacks over events.** BT controller uses callback functions (`status_callback`, `battery_callback`) instead of events. Maintain this pattern.
- **Resource paths via `get_resource_path()`** in `utils/resource_manager.py`. Use this for assets in UI code.
- **Version string format.** Semantic versioning with optional pre-release tags: `v1.2.3`, `v1.2.3-alpha.1`, `v1.2.3-beta.2`, `v1.2.3-rc1`. Parser in `utils/updater.py` supports these formats.

## Important locations

- **Device protocol details:** `bluetooth/constants.py` (BATTERY_PATTERN, MODE_COMMAND_TEMPLATE, timeouts)
- **Build config:** `MiBudsClient.spec` (assets bundling, icon path)
- **UI constants (colors, sizes):** `ui/constants.py`

## Change safety rules

- **Preserve backward compatibility.** Do not change protocol packets or device matching logic without testing on hardware.
- **Do not add external Bluetooth libraries.** Current implementation uses Python's `socket` module directly for RFCOMM. Keep it minimal.
- **GitHub URL is contractual.** Hardcoded in UI constants and used by updater. Changes break update checking and links.
