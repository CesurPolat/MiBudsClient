# Automatic game mode on Wayland

The initial Wayland backend supports **GNOME Shell 46**, including Zorin OS 18
and Ubuntu 24.04. Other Wayland desktops currently report detection unavailable;
manual game mode still works. X11 and Windows retain their existing detectors.

GNOME does not provide ordinary applications with unrestricted foreground-window
access. MiBudsClient includes a small, optional Shell extension that exposes only
the focused application's identity, process ID and fullscreen state on the user
session bus. It does not collect window titles, images, keyboard input or window
history. No Shell unsafe mode or `org.gnome.Shell.Eval` workaround is used.

## Install from source

Run from the repository root, as your normal desktop user:

```sh
python3 tools/install_gnome_bridge.py
```

The helper installs only the two bundled extension files under
`$XDG_DATA_HOME/gnome-shell/extensions/fullscreen@mibudsclient` (by default
`~/.local/share/gnome-shell/extensions/fullscreen@mibudsclient`) and attempts to
enable the extension. If GNOME does not discover a newly installed extension
until the next session, **log out and back in**, then run:

```sh
gnome-extensions enable fullscreen@mibudsclient
```

For a packaged application, obtain `assets/gnome-extension/fullscreen@mibudsclient`
from the source checkout and copy it to the same extension location, then follow
the activation steps above. The extension is optional and installed separately
from the executable.
After updating a loaded extension, log out and back in to load its new code.
The application never installs or enables Shell extensions automatically.

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
