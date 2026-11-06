# AGENTS.md

## Must-follow constraints

- **Windows and Linux support.** Bluetooth discovery can use platform-specific implementations (Windows: PowerShell via `subprocess` + `Get-PnpDevice`, Linux: native Linux-compatible discovery). Keep behavior consistent across supported platforms.
- **Function-list support (user decision).** Show and enable implemented controls from the selected device's `func_list` and its own `extra_data` options. Do not require `VALIDATED_NOISE_MODELS`, `MODEL_BACKENDS`, EQ model allowlists, experimental opt-ins or per-model hardware certification to enable these controls. Unknown/unimplemented functions remain metadata. Hide and disable custom EQ for now, including profile 10 and the band editor. Keep model-specific protocol/label exceptions where evidence requires them; those are not permission lists.
- **Dynamic RFCOMM service discovery.** Resolve the selected device's RFCOMM channel by exact service UUID. `RFCOMM_PORT = 6` in `controllers/bluetooth/constants.py` is only a Redmi Buds 6 Play fallback when no service channel is resolved; record `service_uuid=None` and `resolution_source="profile_fallback"`. Do not infer service/auth from a channel or scan channels blindly.
- **Assets directory bundling.** Build uses `datas=[('assets', 'assets')]` in PyInstaller spec. All UI assets (icon.ico, images) must stay in `assets/` folder.
- **Single instance enforcement.** Application forbids multiple running instances via port 65432. Do not remove or change `check_for_existing_instance()` at app startup.
- **Flet-only UI.** The entire UI layer (including system tray via pystray) depends on Flet. Do not introduce other UI frameworks.

## User workflow and validation

- **Implement first; the user tests.** Make the requested change and hand it back for the user to try. Do not wait for the user to repeat this preference on each task.
- **No unsolicited tests.** Do not add or extend tests, run test suites, perform automated UI/screenshot checks, or launch validation sessions unless the user explicitly requests them. A change request alone does not authorize these activities.
- **No unsolicited builds.** Do not package executables, rebuild demos, or repeat startup/single-instance checks unless explicitly requested. If the user asks to open a demo, prefer running it from source; package it only if necessary to fulfill that request.
- **Keep work proportional.** Use focused source inspection and edits. Avoid repeated verification loops and lengthy progress updates for small changes. Briefly state what changed and that testing is left to the user; do not ask for permission to run tests after every edit.
- **Validation references, when requested.** Package with `flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"`. For single-instance validation, launch the executable twice; the second instance should exit silently and focus the existing window.
- **Hardware testing is evidence, not an activation gate.** Leave hardware testing to the user unless explicitly asked. Do not claim that all devices or packet changes were tested, but do not block catalog-supported implemented controls until every model is tested. Auth is selected from the connected service: command auth for FD2D, raw auth for XiaoAI/standard SPP. An auth failure must not silently fall back to direct commands or another service.

## UI design

- Read `docs/design-system.md` before designing or changing UI. Reuse its shared layout, visual tokens, and interaction patterns. Apply its validation checklist only when the user requests validation; the workflow above takes precedence over automatic testing/build instructions in other repository docs.

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

- **Preserve backward compatibility.** Preserve the working connection and packet paths. Enable implemented controls by catalog capability as requested; report concrete protocol failures honestly without adding per-model validation gates.
- **Do not add external Bluetooth libraries.** Current implementation uses Python's `socket` module directly for RFCOMM. Keep it minimal.
- **GitHub URL is contractual.** Hardcoded in UI constants and used by updater. Changes break update checking and links.
