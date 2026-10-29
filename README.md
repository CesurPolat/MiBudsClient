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
| Battery monitoring | Separate readings for both earbuds and the charging case, charging indicators, and manual refresh. |
| Low latency | Switch Game Mode off, on, or automatically based on the active app. |
| Sound profiles | Read and change the EQ presets offered by your earbuds. |
| Touch controls | Read and edit left and right assignments for single tap, double tap, triple tap, and long press. |
| Desktop notifications | Connection, disconnection, and case-placement updates with battery information and a device image when available. |
| System tray | Keep the app in the background, restore its window, or change low-latency mode from the tray. |
| Everyday conveniences | Automatic connection attempts, run at startup, saved preferences, and a built-in update checker. |
| Localization | 27 locale options across 24 languages, instant switching, and Arabic right-to-left layout. |

## Compatibility

**Redmi Buds 6 Play is the supported device.** The bundled Xiaomi/Redmi catalog provides model names, images, and capability metadata for other products; a catalog entry does not establish control support for that model.

Windows and Linux have platform-specific Bluetooth discovery. Linux tray and notification behavior depends on the desktop environment. Automatic fullscreen detection uses X11 tools and is unavailable in Wayland sessions. Linux hardware and UI validation remains outstanding.

MiBudsClient is an independent community project and is not affiliated with Xiaomi.

## Getting started

1. Pair your **Redmi Buds 6 Play** and connect them in your computer's Bluetooth settings.
2. Download a packaged build for your platform from [Releases](https://github.com/CesurPolat/MiBudsClient/releases), or [run from source](#run-from-source).
3. Launch MiBudsClient. It looks for connected catalog devices and attempts a Bluetooth control connection automatically.
4. Once connected, check the battery cards and choose a low-latency mode. Open **Settings** for gestures, EQ, startup, and language preferences.

Pairing is handled by your operating system. MiBudsClient needs an existing Bluetooth connection before it can communicate with the earbuds.

Only one instance runs at a time. Launching the app again brings the existing window forward. Use the tray's **Quit** command to exit completely.

## Make it yours

### Low-latency mode

- **Off** keeps the earbuds in standard mode.
- **On** enables low latency manually.
- **Auto** enables low latency when a fullscreen app is detected. Add apps as **Include** to enable it for those apps even without fullscreen, or **Exclude** to skip them.

Enable **Wait until app closes** to keep low latency active until the matched app exits. App rules are stored separately for Windows and Linux.

### Sound profiles and custom EQ

Open **Settings → Equalizer** to read the current profile and available presets. Profile changes are acknowledged by the earbuds and checked with a fresh read.

The custom editor appears only when the earbuds return valid custom-band data. When available, releasing a slider previews the draft; **Save** stores it and **Reset** requests a flat curve. Close and reopen the section to recover from a failed operation or reload device settings.

Preset switching was verified on Redmi Buds 6 Play on **2026-10-27**. The tested device returned no custom-band data, so custom EQ preview, save, and reset remain unverified on hardware. See [EQ behavior and validation notes](docs/equalizer.md).

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

On Linux, Bluetooth discovery requires BlueZ's `bluetoothctl`. Tray integration uses PyGObject (`gi`) with AppIndicator3 or GTK. Automatic fullscreen detection also needs `xprop`, `xwininfo`, and `xrandr` in an X11 session. These are system dependencies; `requirements.txt` installs the Python packages only.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| No earbuds found | Confirm Bluetooth is enabled and the earbuds are connected in the system Bluetooth settings, then press **Retry**. |
| Connection times out | Keep the earbuds nearby and powered on. Toggle the computer's Bluetooth off, wait 10 seconds, and turn it back on. If needed, put both earbuds in the case, close it for 5 seconds, then take them out and retry. |
| Battery reading is unavailable | Use **Check Battery** after connecting. Missing readings are treated as unknown. |
| Gesture or EQ request fails | Close and reopen the relevant settings section to read the device state again. |
| Custom EQ is missing | The editor requires valid custom-band data from the earbuds; the tested device did not provide it. Presets can still be available. |
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

Protocol and constant changes also require testing with actual Redmi Buds 6 Play hardware. Synthetic packet tests do not establish device compatibility. Read [AGENTS.md](AGENTS.md) before changing device behavior or packaging.

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
