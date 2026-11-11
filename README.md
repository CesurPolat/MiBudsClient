<div align="center">

[**English**](README.md) · [Türkçe](docs/readme/README.tr.md) · [Deutsch](docs/readme/README.de.md) · [Español](docs/readme/README.es.md) · [Français](docs/readme/README.fr.md) · [Русский](docs/readme/README.ru.md) · [简体中文](docs/readme/README.zh-CN.md)

<img src="assets/icon.png" alt="MiBudsClient icon" width="88">

# MiBudsClient

**Your Xiaomi and Redmi earbuds, on your desktop.**

Battery levels, low latency, sound profiles, and touch controls in one place.<br>
Built with Python and Flet for Windows and Linux.

[**Download**](https://github.com/CesurPolat/MiBudsClient/releases) · [Getting started](#getting-started) · [Run from source](#run-from-source) · [Report an issue](https://github.com/CesurPolat/MiBudsClient/issues)

<img src="docs/MiBudsClientPreview.png" alt="MiBudsClient desktop interface preview" width="720">

</div>

## What you can do

| Feature | What it offers |
| --- | --- |
| Noise control | ANC, transparency and model-specific level options, enabled from the device catalog. Hardware compatibility across models remains unverified. |
| Battery monitoring | Separate readings for both earbuds and the charging case, charging indicators, and manual refresh. |
| Low latency | Switch Game Mode off, on, or automatically based on the active app. |
| Sound profiles | Read and change the EQ presets offered by your earbuds. |
| Touch controls | Read and edit left and right assignments for single tap, double tap, triple tap, and long press. |
| Desktop notifications | Connection, disconnection, and case-placement updates with battery information and a device image when available. |
| System tray | Keep the app in the background, restore its window, or change low-latency mode from the tray. |
| Everyday conveniences | Automatic connection attempts, run at startup, saved preferences, and a built-in update checker. |
| Localization | 27 locale options across 24 languages, instant switching, and Arabic right-to-left layout. |

## Compatibility

**MiBudsClient is built for multiple Xiaomi and Redmi models.** On Windows, it attempts a control connection to recognized catalog devices and enables implemented controls from each model's feature list and options. A separate model approval list is not required.

| Area | Current scope |
| --- | --- |
| Model recognition | Names, VID/PID identities, images and capability data come from the [device catalog](assets/device_catalog.json). Recognition alone does not guarantee a working protocol session. |
| Implemented controls | Battery monitoring, ANC/transparency, EQ presets, supported touch gestures and low latency. Controls and choices depend on the model; battery readings depend on what the device reports. |
| Windows connection | Discovers the RFCOMM channel from the device's Bluetooth service. Supports command authentication on MIUI SPP (FD2D) and raw authentication on XiaoAI/standard SPP. |
| Linux connection | Bluetooth discovery and the existing Redmi Buds 6 Play channel-6 fallback are available. Dynamic RFCOMM service discovery is currently Windows-only; general multi-model connectivity is not yet implemented on Linux. |
| Hardware evidence | Redmi Buds 6 Play is the project's hardware reference, with recorded battery/low-latency use and dated EQ/gesture checks below. This does not establish every feature on every model; ANC/transparency and raw authentication still need hardware confirmation. |

Custom EQ is deferred and hidden, including the custom preset. Other catalog features do not become app controls automatically. Feature availability comes from the catalog; connection success and the device's replies determine whether an operation can complete. Firmware and regional variants can differ.

Linux tray and notification behavior depends on the desktop environment. Automatic fullscreen detection uses X11 tools and is unavailable in Wayland sessions. Linux hardware and UI validation remains outstanding.

This README describes the current source; older packaged releases may not include these changes. See [device capabilities](docs/device-capabilities.md), [command authentication](docs/command-auth.md) and [raw authentication](docs/raw-auth.md) for technical details.

MiBudsClient is an independent community project and is not affiliated with Xiaomi.

## Getting started

1. Pair your Xiaomi or Redmi earbuds and connect them in your computer's Bluetooth settings.
2. Download a packaged build for your platform from [Releases](https://github.com/CesurPolat/MiBudsClient/releases), or [run from source](#run-from-source).
3. Launch MiBudsClient. It looks for connected catalog devices and attempts a Bluetooth control connection automatically.
4. Once connected, check the battery cards and the controls available for your model. Open **Settings** for supported gestures, EQ, noise control, startup, and language preferences.

Pairing is handled by your operating system. MiBudsClient needs an existing Bluetooth connection before it can communicate with the earbuds.

Only one instance runs at a time. Launching the app again brings the existing window forward. Use the tray's **Quit** command to exit completely.

## Make it yours

### Low-latency mode

- **Off** keeps the earbuds in standard mode.
- **On** enables low latency manually.
- **Auto** enables low latency when a fullscreen app is detected. Add apps as **Include** to enable it for those apps even without fullscreen, or **Exclude** to skip them.

Enable **Wait until app closes** to keep low latency active until the matched app exits. App rules are stored separately for Windows and Linux.

### Sound profiles

Open **Settings → Equalizer** to read the current profile and select the presets listed for your model. Profile changes are acknowledged by the earbuds and checked with a fresh read.

**Custom EQ is planned for a later version.** The band editor and custom preset are currently hidden, even if the catalog lists them.

Preset switching was verified on Redmi Buds 6 Play on **2026-10-27**; this is not hardware confirmation for other models. See [EQ technical notes](docs/equalizer.md) for earlier implementation and validation details.

### Touch gestures

Open **Settings → Gestures** to load assignments from the earbuds. Each supported gesture has separate left and right selectors, with choices taken from the exact model's catalog record. Changes are sent immediately and shown as saved only after the assignment is read back. Assignments live on the earbuds. ANC cycle editing is outside the current implementation.

Reading assignments and writing their existing values back were verified on Redmi Buds 6 Play on **2026-10-26**. Changing to a different function and physically triggering it still require manual verification.

### Notifications

Connection and case-change notifications include battery levels when available. Case placement and removal are inferred from each earbud's charging flag; the app does not read a separate case or wearing sensor. Disconnect notices use the last known battery readings.

Clicking a notification restores the app window. On Linux, this requires a notification server that supports default actions. OS notification sounds are suppressed; the app plays its own charging-transition melodies and a one-time melody on the first successful earbud connection of each app session.

### Language

Choose **Settings → Language → System language**, or select a language by its native name. The choice is saved and applies immediately to the interface, tray menu, and future notifications. Unsupported system languages fall back to English.

Available languages: Arabic, Chinese (Simplified, Taiwan, Hong Kong), Dutch, English, Estonian, Finnish, French, German, Hindi, Hungarian, Indonesian, Italian, Japanese, Korean, Malay, Polish, Portuguese (Brazil and Portugal), Russian, Spanish, Swedish, Thai, Turkish, Ukrainian, and Vietnamese.

## Run from source

You need Python with `venv` and `pip`, a Bluetooth adapter, and earbuds already connected through the operating system.

```sh
git clone https://github.com/CesurPolat/MiBudsClient.git
cd MiBudsClient
```

**Windows — PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

**Linux**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

On Linux, Bluetooth discovery requires BlueZ's `bluetoothctl`. Tray integration prefers PyGObject (`gi`) with GTK 3 and AppIndicator3 or AyatanaAppIndicator3, then falls back to GTK's legacy tray or Xorg when available. Desktop tray support is still required; Xorg has limited menu support. Missing tray dependencies do not prevent startup. Until the tray is ready, closing the window minimizes it with its taskbar entry retained; an unexpected tray shutdown restores the window. An explicit `PYSTRAY_BACKEND` setting is respected. Automatic fullscreen detection also needs `xprop`, `xwininfo`, and `xrandr` in an X11 session. These are system dependencies; `requirements.txt` installs the Python packages only.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| No earbuds found | Confirm Bluetooth is enabled and the earbuds are connected in the system Bluetooth settings, then press **Retry**. |
| Connection times out | Keep the earbuds nearby and powered on. Toggle the computer's Bluetooth off, wait 10 seconds, and turn it back on. If needed, put both earbuds in the case, close it for 5 seconds, then take them out and retry. |
| Battery reading is unavailable | Use **Check Battery** after connecting. Missing readings are treated as unknown. |
| Gesture or EQ request fails | Close and reopen the relevant settings section to read the device state again. |
| Custom EQ is missing | Custom EQ is deferred and hidden in this version. Model-supported presets remain available. |
| Auto mode does not switch on Linux | Check that you are using X11 and the fullscreen-detection tools above are installed. Wayland detection is unavailable. |
| Clicking a Linux notification does nothing | Check whether your desktop notification server supports default actions. Restore the window through the tray. |

When [reporting an issue](https://github.com/CesurPolat/MiBudsClient/issues), include the app version, OS and desktop session, earbud model, steps to reproduce, and any error details shown by the app.

## Development

The project separates Bluetooth communication, application controllers, and Flet UI components:

```text
main.py                 Application startup and wiring
controllers/bluetooth/  Discovery, RFCOMM transport, and device protocol
controllers/device/     Connection state, catalog sync, and battery updates
controllers/latency/    Manual and automatic low-latency control
controllers/settings/   Gesture and EQ operations
ui/                     Flet screens, components, tray, and notifications
utils/                  Preferences, localization, updates, and platform helpers
assets/                 Bundled icons, images, device catalog, and locale files
tests/                  Automated tests
docs/                   Preview assets and technical notes
```

Run the automated suite from the repository root in your development environment:

```sh
python -m unittest discover -s tests
```

When testing protocol changes, record the exact model, firmware, OS, connection method and feature exercised. Synthetic packet tests do not establish hardware compatibility; hardware reports are evidence, not a per-model activation gate. Read [AGENTS.md](AGENTS.md) before changing device behavior or packaging.

README translations live in `docs/readme/`. Update them alongside the English README when features or installation instructions change.

Translations live in `assets/locales/`. See the [localization guide](docs/localization.md) for stable keys, placeholders, Xiaomi resource imports, and review notes.

### Build a standalone executable

With the Flet CLI available in your active environment, run on the target platform:

**Windows — PowerShell**

```powershell
flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"
```

**Linux**

```sh
flet pack main.py --icon assets/icon.ico --add-data "assets:assets" --name "MiBudsClient" --hidden-import optparse
```

Keep all UI resources under `assets/` so they are included in the package. Before shipping, launch the executable, verify its behavior with the earbuds, then launch it a second time to check that it focuses the existing window and exits silently.

## License

MiBudsClient is licensed under the [GNU General Public License v3.0](LICENSE).
