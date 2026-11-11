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
