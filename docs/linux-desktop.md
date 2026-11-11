# Linux tray and notifications

Tray icons and desktop notifications use separate services. A tray icon requires
a panel or shell that hosts it. Notifications require a session service named
`org.freedesktop.Notifications`. Neither service is guaranteed by Wayland or X11
alone. MiBudsClient does not install panels, shell extensions for tray hosting,
notification daemons, or system packages automatically.

## Tray availability

AppIndicator/Ayatana is preferred, with GTK and Xorg fallbacks as before.
For AppIndicator, the app checks the StatusNotifierWatcher's
`IsStatusNotifierHostRegistered` property using `gdbus`. GTK's legacy backend is
checked through its embedded state on the GTK loop. Xorg uses pystray's current
tray-manager reference. These probes are isolated in `utils/tray_host.py` because
some backend integration uses private pystray attributes.

Until hosting is detected, closing the window minimizes it and keeps a taskbar
entry. If a previously working tray host disappears, the window is restored.
The tray loop remains alive and availability is refreshed when the host returns.
This is a best-effort hosting check, not proof that every panel renders every
icon or supports every menu feature. The Xorg backend still has limited native
menu support.

## Notifications without a tray

Linux notifications use Gio/GLib from PyGObject on a dedicated worker and GLib
context, independent of pystray's icon, private notifier, and native GTK loop.
Gio/GLib is required; GTK widgets are not. `GetCapabilities` determines whether
the server supports clickable actions and body markup. A server without actions
still receives the notification, without claiming click-to-open support.

The request includes `suppress-sound` when silent delivery is requested, including
image-to-text retry paths. The notification server ultimately controls how
notifications, images, actions and sound hints are presented. Text remains when a
cached image is missing; a rejected image is retried once without an image.
Python capture does not control notification-server or desktop policy.

Only IDs sent by MiBudsClient can activate its window. Closed notifications are
removed, and daemon owner changes clear tracked IDs to prevent stale ownership
when a restarted daemon reuses an ID. Application shutdown stops the worker and
disconnects its signals. Calls and queue sizes are bounded; failures are logged
and subsequent notifications can retry.

Windows retains the existing native tray and notification path. The Linux
protocol and lifecycle tests use fake services and do not establish compatibility
with every GNOME, KDE, Sway or Hyprland session.

References: [Desktop Notifications](https://specifications.freedesktop.org/notification/latest-single/),
[StatusNotifierWatcher](https://specifications.freedesktop.org/status-notifier-item/latest/status-notifier-watcher.html),
[KDE watcher properties](https://github.com/KDE/plasma-workspace/blob/master/xembed-sni-proxy/org.kde.StatusNotifierWatcher.xml).

## Window/taskbar icon

The tray icon is independent of the window's taskbar/dock icon. Flet 0.82's
`page.window.icon` API affects Windows only. Its prebuilt Linux GTK client uses
`com.appveyor.flet`, so an AppDir entry with only `Name`, `Exec` and `Icon` does
not establish a matching runtime identity on GNOME Wayland.

Before launching Flet, MiBudsClient registers a hidden user desktop entry and
copies `assets/icon.png` to a stable user data path. Its icon path never points
to an expired AppImage mount or PyInstaller extraction directory. The launch
command uses `APPIMAGE` when available, otherwise the frozen executable or the
source interpreter and script. The existing single-instance guard runs first.

Flet 1.x uses `FLET_APP_ID=dev.mibuds.client`. With the current Flet 0.x client,
a temporary compatibility entry also matches `com.appveyor.flet`; this shared
legacy identity can cause other old Flet windows to share the label/icon while
MiBudsClient is running. A unique native Linux client identity or a separately
validated Flet upgrade is needed to eliminate that old-client limitation. The
app never rewrites the shared Flet binary or shadows existing user/system entries.

Owned runtime entries are removed on normal shutdown, unless modified by the
user while the app was running. This enables the running-window icon; it does
not install a permanent launcher for pinning. A persistent installer/AppImage
integration should install the matching desktop file and themed icon. The
provided `assets/linux/dev.mibuds.client.desktop` is the template for a client
built with the application's own identity, with an icon named
`dev.mibuds.client.png` in the AppDir/icon theme. Source assets remain in `assets/`.

Existing executable/AppImage artifacts do not change when source files change.
They must be repackaged to include the runtime fix. No executable is rebuilt by
the desktop registration helper.

## AppImage packaging

The AppDir recipe is tracked in this repository: `assets/linux/AppRun`,
`assets/linux/dev.mibuds.client.desktop`, and `tools/build_appimage.sh`.
The script recreates the former external AppDir layout using `assets/icon.png`
and the current **one-file Linux executable** at `dist/MiBudsClient`. It does
not read or modify `~/Desktop/MiBudsClient.AppDir` and does not compile the app.

From the repository root, first package the current source using the virtualenv
Python (with Flet CLI and PyInstaller installed). The builder includes the Linux
tray backends without opening a display, exposes distro PyGObject after virtualenv
packages, and limits bundled GTK icons/themes to avoid copying the entire desktop
theme collection. It replaces the generated `build/` and `dist/` directories.
The build machine needs PyGObject, GTK 3 introspection, and the appropriate
AppIndicator/Ayatana introspection packages installed.

```sh
python tools/build_linux.py
```

To prepare only `build/MiBudsClient.AppDir`:

```sh
bash tools/build_appimage.sh --prepare-only
```

To prepare the AppDir and generate `dist/MiBudsClient-<architecture>.AppImage`,
install `appimagetool` separately and run:

```sh
bash tools/build_appimage.sh
# Alternatively, point to an executable appimagetool outside PATH:
APPIMAGETOOL="/absolute/path/to/appimagetool-x86_64.AppImage" bash tools/build_appimage.sh
```

The script replaces the generated `build/MiBudsClient.AppDir` on each run.
Generated AppDirs and AppImages are ignored by Git; launcher templates and
source assets remain tracked. Rebuild the executable before packaging source
changes; wrapping an old executable does not include the new fixes.
This preserves the existing packaging approach and does not bundle additional
system libraries or install desktop integration. Linux dependencies described
above still apply, including the current Flet client identity limitation.
