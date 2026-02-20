# MiBuds Client

A lightweight Python and Flet-based desktop client for Redmi Buds 6 Play. This application allows you to monitor your earbuds' status and manage settings via Bluetooth.

## Features

- **Battery Tracking:** Real-time display of battery percentages for left earbud, right earbud, and charging case.
- **Charging Status:** Indicators showing whether the earbuds or case are currently charging.
- **Low Latency Mode:** Quick toggle for Game Mode (Low Latency).
- **Auto-Connect:** Automatically detects compatible connected Bluetooth devices.
- **Modern UI:** A sleek, dark-themed interface built with the Flet framework.

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

## Building the Executable

To package the application into a standalone executable for Windows, run the following command:

```bash
flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"
```

## Supported Devices

- Redmi Buds 6 Play
- *(Untested on other Xiaomi/Redmi models, but may work if they use a compatible RFCOMM protocol)*

## License

This project is licensed under the GNU General Public License v3.0 (GPLv3). See the [LICENSE](LICENSE) file for details.

---
**Note:** This is not an official Xiaomi application. It is developed for personal use and the open-source community.
