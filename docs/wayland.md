# Automatic game mode on Wayland

The initial Wayland backend supports **GNOME Shell 46**, including Zorin OS 18
and Ubuntu 24.04. Other Wayland desktops currently report detection unavailable;
manual game mode still works. X11 and Windows retain their existing detectors.

GNOME does not provide ordinary applications with unrestricted foreground-window
access. MiBudsClient includes a small, optional Shell extension that exposes only
the focused application's identity, process ID and fullscreen state on the user
session bus. It does not collect window titles, images, keyboard input or window
history. No Shell unsafe mode or `org.gnome.Shell.Eval` workaround is used.

## Automatic setup

On application startup, the monitor's background worker detects the desktop
session. X11 and Windows do not install a Shell extension. On GNOME Shell 46
Wayland, MiBudsClient automatically copies its two bundled extension files from
`assets/gnome-extension/fullscreen@mibudsclient` into the current user's extension
directory, then enables the bridge. This also works from the PyInstaller bundle;
no source checkout, terminal command or administrator access is required.

The destination is `$XDG_DATA_HOME/gnome-shell/extensions/fullscreen@mibudsclient`
(default `~/.local/share/gnome-shell/extensions/fullscreen@mibudsclient`). Only
changed files are replaced. Other extensions and their preferences are preserved.

If GNOME has not discovered the new extension in the current session, the app
registers it for the next login and displays a localized instruction to **log out
and back in**. No activation command is needed after login. Updates to an already
loaded bridge can also require a new desktop session. The app does not restart
the desktop or close the user's applications.

If the user subsequently disables the bridge, or disables extensions globally,
automatic setup preserves that preference. Re-enable it in GNOME's Extensions app
when desired. Unsupported GNOME versions, other Wayland compositors, missing
system tools and read-only user directories do not prevent application startup;
manual game mode remains available. This setup does not install OS packages.

Developers can run the same setup manually using the application's Python
environment, from the repository root:

```sh
python tools/install_gnome_bridge.py
```

Choose **Automatic** in MiBudsClient and start a fullscreen application. Detection
uses the existing polling and stabilization interval. With **Wait until app
closes** disabled, returning to the desktop should restore standard mode. With
that setting enabled, the existing process-hold policy still applies.
The bridge reports no foreground game while GNOME's overview or lock screen is
active. Executable names from `/proc` are preferred for application rules, with
the compositor's application identity used as a fallback.

If the bridge or `gdbus` is missing, disabled, times out or returns invalid data,
the monitor reports unknown state rather than claiming a game is open or closed.
It retries on subsequent polls, so enabling the bridge does not require an app
restart. To disable this integration:

```sh
gnome-extensions disable fullscreen@mibudsclient
```

Software tests use synthetic D-Bus responses and do not validate a live GNOME
Shell session. GNOME versions other than 46 and other Wayland compositors have
not been enabled by this implementation.

References: [GNOME extension lifecycle](https://gjs.guide/extensions/development/creating.html),
[GJS D-Bus](https://gjs.guide/guides/gio/dbus.html),
[Meta.Window API](https://gnome.pages.gitlab.gnome.org/mutter/meta/class.Window.html).
