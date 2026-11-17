---
name: Bug report
about: Report a connection, device control, or desktop app problem.
title: ''
labels: ''
assignees: ''
---

<!-- Search existing issues first. You can write in your preferred language.
Fill in what you know; "Unknown" or "Not applicable" is fine.
You do not need to collect protocol captures or run hardware tests. -->

### What went wrong?

<!-- Describe one problem and any error message exactly as shown.
Which area is affected: discovery/connection, battery, noise control, EQ presets,
touch gestures, manual/Auto low latency, tray, notifications, startup, updates,
language, or another part of the interface? -->

### Steps to reproduce

1.
2.
3.

### Expected and actual behavior

- Expected:
- Actual:
- How often does it happen? (Every time / Sometimes / Once / Unknown):

### App and system

- MiBudsClient version (or commit if running from source):
- Installation (downloaded release / source / other):
- OS and version (Windows version or Linux distribution):
- Linux only: desktop environment and version, X11 or Wayland:
- Source only: Python version and launch command, if known:

### Earbuds and connection

<!-- Skip this section for issues unrelated to earbuds or Bluetooth.
Use the exact model name; similar models can have different controls. -->

- Earbuds model:
- Firmware version and regional variant, if known:
- Are the earbuds connected in the computer's Bluetooth settings?
- Does audio playback through the earbuds work?
- Does MiBudsClient find the device? What connection status does it show?
- Bluetooth adapter and driver version, if known:
- Is another phone or earbud app also connected?

### Details for the affected feature

<!-- Answer only the relevant prompts and delete the rest.

- Battery: which reading is wrong (left/right/case), what is displayed,
  whether the earbuds are charging/in the case, and whether Check Battery helps.
- Noise control / EQ / gestures: is the control missing, disabled, or failing?
  Give the exact mode, preset, or gesture/action. For gestures, include left/right.
  Does the setting revert, show an error, or appear saved without affecting the earbuds?
  Custom EQ and the band editor are currently hidden by design.
- Low latency: Off/On/Auto, whether manual switching works, the affected app,
  fullscreen state, Include/Exclude rules, and Wait until app closes setting.
- Tray / notifications / window: what action triggered it (close, minimize,
  notification click, etc.) and whether the tray icon/notification appeared.
  On Linux, include your panel/tray extension or notification service if known.
- Language / layout: selected language, affected text/screen, display scaling,
  and window size if relevant. Screenshots help here.
- Startup / updates: launch method, current/target version, and the exact error.
-->

### Logs and screenshots (optional)

<!-- Press F12 to open runtime logs. On Linux, focus the app first.
Paste relevant lines around the failure in a fenced code block, or attach a text file.
If the app cannot start, include terminal output if available.
Review logs/screenshots before posting: remove Bluetooth addresses, usernames,
personal paths, tokens, and authentication payloads. -->

### Previous behavior and workarounds (optional)

<!-- Did this work before? Include the last working app version and any change
around when it broke (app, firmware, OS, driver). Describe anything you already
tried and whether it helped; repeating troubleshooting steps is not required. -->
