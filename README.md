# MiBudsClient

A Python & Flet-based desktop client for Redmi Buds 6 Play. Features real-time battery tracking and low-latency mode via Bluetooth.

## Features

- **Battery Tracking:** Real-time display of battery percentages for left earbud, right earbud, and charging case.
- **Charging Status:** Indicators showing whether the earbuds or case are currently charging.
- **Low Latency Mode:** Off, Auto, and On modes for controlling Game Mode (Low Latency). Auto mode uses a single app list with Exclude/Include behavior and supports keeping low latency active until the app closes.
- **System Tray Support:** Minimize to tray and control features like Low Latency Mode directly from the tray menu.
- **Auto-Connect:** Automatically detects compatible connected Bluetooth devices.
- **Single Instance Protection:** Prevents multiple instances of the application from running simultaneously.
- **Windows Startup Support:** Option to start the application automatically when Windows boots.
- **Smart Updater:** Built-in update checker that supports semantic versioning, including pre-release tags like `alpha`, `beta`, and `rc`.
- **Modern UI:** A sleek, dark-themed interface built with the Flet framework.
- **Languages:** 27 locale options covering 24 languages, with instant language switching and Arabic right-to-left layout.

## Language settings

Open **Settings → Language** to choose **System language** or a language shown
in its native name. The default follows the operating system; unsupported
languages fall back to English. Your choice is saved and applies immediately to
the screens, tray menu, and future notifications without reconnecting the earbuds.
Technical logs, device names, process names, and raw error details are preserved.

Translation catalogs live in `assets/locales/{language}.json` and are included by
the existing assets packaging rule. Use stable keys and named placeholders in all
catalogs. UI text uses `utils.i18n.t()`; controller messages use
`utils.i18n.message()`, a string-compatible value retaining its key and parameters.
Use `render()` at the display boundary and `refresh_translations()` to update
existing controls. Keep nested messages intact instead of interpolating them into
f-strings. Catalog integrity and live-switch tests run with
`python -m unittest discover -s tests`.

The supported languages are Arabic, Chinese (Simplified, Taiwan, Hong Kong),
Dutch, English, Estonian, Finnish, French, German, Hindi, Hungarian, Indonesian,
Italian, Japanese, Korean, Malay, Polish, Portuguese (Brazil and Portugal), Russian,
Spanish, Swedish, Thai, Turkish, Ukrainian, and Vietnamese.
Equivalent earbud terms were checked against the supplied Xiaomi Earbuds XML
resources; desktop-specific messages are separately authored. See
[translation sources and review notes](docs/localization.md) for import instructions
and the distinction between original resources and desktop translations.

## Device catalog

`assets/device_catalog.json` contains the complete app product response and is
the primary source for exact VID/PID model names and metadata. It is bundled
with the other assets. The SDK table in `controllers/bluetooth/device_catalog.py` remains a
fallback for identities absent from the app response.

`get_device_models(vid, pid)` (or `DeviceIdentity.models`) returns independent
copies of the matching app records, including `model`, `pattern`, `pdid`,
`func_list`, `extra_info`, icons and platform/version fields. VID/PID arguments
are integers; the source JSON stores them as hexadecimal strings. Function
`extra_data` stays in its original JSON-string form and can be decoded with
`json.loads()` when needed. SDK-only identities return no app metadata.

Catalog recognition does not enable device control or interpret function IDs;
Bluetooth control remains specific to Redmi Buds 6 Play.

## Downloads

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/3767c651-d965-4450-b191-1369292c8383" width="400"></td>
  </tr>
  <tr>
    <td><a href="https://github.com/CesurPolat/MiBudsClient/releases"><img src="https://github.com/user-attachments/assets/abf831bc-7329-435a-a398-b1f6c706ca0d" width="200"></a></td>
  </tr>
</table>

## Installation

1. Clone or download this repository:
   ```bash
   git clone https://github.com/CesurPolat/MiBudsClient.git
   cd MiBudsClient
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the following command in your terminal to start the application:

```bash
python main.py
```

Upon launch, the app will automatically scan for your device and attempt to connect. Once connected, battery levels will be displayed on the screen.

Open **Settings → Earbud Management → Gestures** to read touch assignments from
Redmi Buds 6 Play. Single tap, double tap, triple tap, and long press have separate left and right
selectors. Options come from the exact model's catalog record. Changes are sent
immediately and reported as saved only after reading the assignment back from
the earbuds. Close and reopen **Gestures** to retry a failed request. Assignments are
stored on the earbuds, not in local preferences; ANC cycle editing is excluded.

The gesture packets were derived from APK analysis. On 2026-10-26, a connected
Redmi Buds 6 Play successfully returned its assignments and acknowledged eight
same-value writes (both sides of single tap, double tap, triple tap, and long press), each
verified by a fresh read. Changing to a different function and physically
triggering that gesture still need manual verification. Linux hardware/UI
validation is also outstanding.

## Building the Executable

To package the application into a standalone executable for Windows, run the following command:

```bash
flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"
```

```bash
flet pack main.py \
  --icon assets/icon.ico \
  --add-data "assets:assets" \
  --name "MiBudsClient" \
  --hidden-import optparse
```

## Supported Devices

- Redmi Buds 6 Play
- *(Untested on other Xiaomi/Redmi models, but may work if they use a compatible RFCOMM protocol)*

## License

This project is licensed under the GNU General Public License v3.0 (GPLv3). See the [LICENSE](LICENSE) file for details.

---
**Note:** This is not an official Xiaomi application. It is developed for personal use and the open-source community.
