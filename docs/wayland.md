# Automatic game mode on Wayland

Wayland detection chooses the current compositor automatically:

| Desktop | Interface and requirements |
| --- | --- |
| GNOME Shell 46, Zorin OS 18, Ubuntu 24.04 | Bundled Shell bridge, installed automatically |
| KDE Plasma 6 | `kdotool` with the `kwinscript --file` command; bundled read-only KWin query |
| Sway | `swaymsg -r -t get_tree` |
| Hyprland | `hyprctl -j activewindow` |

X11 and Windows retain their existing detectors. Other Wayland compositors and
GNOME versions currently report detection unavailable; manual game mode remains
available. These backends do not query XWayland as a substitute for native windows.

Sway and Hyprland use tools normally supplied by their compositor packages and
need no MiBudsClient extension. KDE needs a recent `kdotool` that supports custom
scripts; versions without `kwinscript` are insufficient. MiBudsClient does not
install OS packages or download executables. Install missing system tools using
your distribution's package manager. The KDE query reads `workspace.activeWindow`
and `fullScreen` without changing windows or installing a persistent KWin plugin.
`kdotool` manages its temporary script lifecycle. Plasma 5 is not supported by
this query.

The focused window's compositor fullscreen state is used, so a maximized
Hyprland window is not treated as fullscreen. Sway supports floating windows,
XWayland WM_CLASS fallback and a focused child inside a fullscreen container.
No focused window reports false; malformed data, missing tools and timeouts
report unknown. The existing include/exclude and process-hold policies apply
to every backend. Lock-screen/overview suppression is implemented by the GNOME
bridge; equivalent behavior is not asserted for the other compositors.

GNOME does not provide ordinary applications with unrestricted foreground-window
access. MiBudsClient includes a small, optional Shell extension that exposes only
the focused application's identity, process ID and fullscreen state on the user
session bus. It does not collect window titles, images, keyboard input or window
history. No Shell unsafe mode or `org.gnome.Shell.Eval` workaround is used.

## Automatic setup

On application startup, the monitor's background worker detects the desktop
session. X11, Windows, KDE, Sway and Hyprland do not install a GNOME Shell extension. On GNOME Shell 46
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
when desired. Unsupported desktop versions/compositors, missing
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

Software tests use synthetic D-Bus and compositor JSON responses. The GNOME 46
bridge has been exercised on the user’s Zorin session. KDE Plasma, Sway and
Hyprland have not been verified in live desktop sessions.

References: [GNOME extension lifecycle](https://gjs.guide/extensions/development/creating.html),
[GJS D-Bus](https://gjs.guide/guides/gio/dbus.html),
[Meta.Window API](https://gnome.pages.gitlab.gnome.org/mutter/meta/class.Window.html).

Additional references: [kdotool](https://github.com/jinliu/kdotool), [KWin API](https://develop.kde.org/docs/plasma/kwin/api/), [Sway IPC](https://github.com/swaywm/sway/blob/master/sway/sway-ipc.7.scd), [Hyprland IPC](https://wiki.hypr.land/IPC/).
