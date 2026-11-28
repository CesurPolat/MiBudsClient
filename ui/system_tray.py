"""System tray icon and menu."""

from typing import Callable, Optional
import threading
import sys
from utils.app.i18n import t, render
from utils.notifications.image_notifications import ImageNotifications
from utils.notifications.linux_notifications import LinuxNotifications
from utils.desktop.tray_host import TrayHostMonitor
from controllers.battery.stream import BATTERY_UNKNOWN, battery_state
from controllers.equalizer.protocol import PROFILE_KEYS

from utils.desktop.tray_backend import load_tray_module

# pystray chooses its backend during import, so configure it first.
pystray = load_tray_module()

from utils.app.resource_manager import load_pil_image
from .constants import TRAY_ICON_PATH, TRAY_ICON_SIZE


class SystemTray:
    """Manages the system tray icon and menu."""
    
    def __init__(
        self, 
        on_show: Callable, 
        on_exit: Callable,
        on_latency_mode_select: Optional[Callable[[str], None]] = None,
        get_latency_mode: Optional[Callable[[], str]] = None,
        latency_available: Callable[[], bool] = lambda: False,
        on_device_action: Optional[Callable[[dict], None]] = None,
    ):
        self.on_device_action = on_device_action
        self._state_lock = threading.Lock()
        self._state = {}
        self.latency_available = latency_available
        self.on_show = on_show
        self.on_exit = on_exit
        self.on_latency_mode_select = on_latency_mode_select
        self.get_latency_mode = get_latency_mode
        self.icon = None
        self._stopped = threading.Event()
        self._ready = threading.Event()
        self._device = ("Redmi Buds 6 Play", "")
        self._device_lock = threading.Lock()
        self._image_notifications = ImageNotifications(on_activate=self.on_show)
        self._linux_notifications = LinuxNotifications(on_activate=self.on_show) if sys.platform.startswith("linux") else None
        self._host_monitor = None

    @property
    def available(self) -> bool:
        return self._ready.is_set() and not self._stopped.is_set()
    
    def run(self) -> None:
        """Start the system tray icon."""
        if self._stopped.is_set() or pystray is None:
            return
        try:
            # Tray uses default icon.png
            tray_image = load_pil_image(TRAY_ICON_PATH, TRAY_ICON_SIZE)

            has_menu = bool(getattr(pystray.Icon, "HAS_MENU", False))
            if has_menu:
                menu = self._build_menu()
            else:
                print(
                    f"Tray backend has no menu support: {pystray.Icon.__module__}. "
                    "Open/Quit options in tray menu are unavailable."
                )
                menu = pystray.Menu(
                    pystray.MenuItem(lambda item: t("tray.open"), lambda icon, item: self.on_show(), default=True)
                )
            
            self.icon = pystray.Icon("MiBudsClient", tray_image, self._tooltip(), menu)
            try:
                self._image_notifications.bind(self.icon)
            except Exception as error:
                print(f"Tray notification integration unavailable: {error}")
            def setup(icon):
                if self._stopped.is_set():
                    icon.stop()
                else:
                    try:
                        icon.visible = True
                        if sys.platform.startswith("linux") and type(icon).__module__ in {
                            "pystray._appindicator", "pystray._gtk", "pystray._xorg",
                        }:
                            self._host_monitor = TrayHostMonitor(icon, lambda state: self._host_state(icon, state))
                            self._host_monitor.start()
                        else:
                            self._ready.set()
                            self.refresh_menu()
                    except Exception as error:
                        print(f"Tray icon unavailable: {error}")
                        self.on_show()
                        icon.stop()

            self.icon.run(setup=setup)
        except Exception as e:
            print(f"Tray error: {e}")
        finally:
            if self._host_monitor:
                self._host_monitor.stop()
            self._ready.clear()
            self.icon = None
            try:
                if not self._stopped.is_set():
                    self.on_show()
            finally:
                try:
                    self._image_notifications.close()
                except Exception as error:
                    print(f"Tray notification cleanup failed: {error}")

    def _host_state(self, icon, available):
        if self._stopped.is_set() or self.icon is not icon:
            return
        was_ready = self._ready.is_set()
        if available:
            self._ready.set()
            if not was_ready:
                self.refresh_menu()
        else:
            self._ready.clear()
            if was_ready:
                self.on_show()
    
    def _get_mode(self) -> str:
        """Get current latency mode."""
        if self.get_latency_mode:
            return self.get_latency_mode() or "off"
        return "off"

    def _is_mode(self, mode: str) -> bool:
        return self._get_mode() == mode

    def _on_mode_select(self, mode: str) -> None:
        """Select latency mode from tray menu."""
        if self.latency_available() and self.on_latency_mode_select:
            self.on_latency_mode_select(mode)

    def set_state(self, state: dict) -> None:
        """Accept an owned snapshot, never live Flet controls or controller data."""
        with self._state_lock:
            if self._state == state:
                return
            self._state = state
        self.refresh_menu()

    @staticmethod
    def _battery_values(state):
        values = {}
        for side, raw in zip(("left", "right", "case"), state.get("battery", (BATTERY_UNKNOWN,) * 3)):
            if state.get("single_body"):
                if side != "left":
                    continue
                side = "device"
            value = battery_state(raw)
            if side == "case" and value is None:
                continue
            label = str(t("notification.battery_percent", percent=value[0])) if value else "\u2014"
            if value and value[1]:
                label = str(t("notification.battery_charging", level=label))
            values[side] = label
        return values

    def _tooltip(self):
        with self._state_lock:
            state = self._state
        if not state.get("connected"):
            return f'Mi Buds Client\n{t("eq.disconnected")}'
        lines = [f'{t("battery." + side)}: {value}'
                 for side, value in self._battery_values(state).items()]
        return "Mi Buds Client\n" + "\n".join(lines)

    def _build_menu(self):
        with self._state_lock:
            state = self._state
        item = pystray.MenuItem
        separator = pystray.Menu.SEPARATOR
        connected = state.get("connected", False)
        entries = [item(str(t("tray.open")), lambda icon, entry: self.on_show(), default=True)]
        if not connected:
            entries.append(item(str(t("eq.disconnected")), None, enabled=False))
        else:
            batteries = self._battery_values(state)
            summary = " · ".join(f'{t("battery." + side)}: {value}'
                                 for side, value in batteries.items())
            entries.append(item(summary, None, enabled=False))
        entries.append(separator)

        def action(feature, operation, **values):
            # Bind the snapshot's session, so an old open menu cannot affect a new device.
            request = {"session": state.get("session"),
                       "feature": feature, "operation": operation, **values}
            def invoke(icon, entry):
                if self.on_device_action and not self._stopped.is_set():
                    self.on_device_action(dict(request))
            return invoke

        def choice(label, callback, selected, enabled):
            return item(str(label), callback, checked=lambda entry: selected,
                        radio=True, enabled=enabled)

        def group(title, children):
            if not children:
                return
            if getattr(pystray.Icon, "HAS_SUBMENU", True):
                entries.append(item(str(title), pystray.Menu(*children)))
            else:
                entries.extend([item(str(title), None, enabled=False), *children, separator])

        def feedback(feature, data, children):
            if data.get("busy"):
                key = "eq.working" if feature == "eq" else "noise.working"
                children.append(item(str(t(key)), None, enabled=False))
            elif data.get("error"):
                children.append(item(data["error"], None, enabled=False))
            if feature != "eq":
                children.append(item(str(t("noise.refresh")), action(feature, "read"),
                                     enabled=connected and data.get("can_read", False)))

        eq = state.get("eq", {})
        if eq.get("visible"):
            children = [choice(t("eq." + PROFILE_KEYS[p]), action("eq", "profile", profile=p),
                               eq.get("current") == p, connected and eq.get("enabled", False))
                        for p in eq.get("profiles", ())]
            current = eq.get("current")
            if current is not None and current != 10 and current not in eq.get("profiles", ()):
                children.append(item(str(t("eq.current", code=f"{current:02X}")), None, enabled=False))
            feedback("eq", eq, children)
            group(t("eq.title"), children)

        noise = state.get("noise", {})
        if noise.get("modes"):
            enabled = connected and noise.get("enabled", False)
            children = [choice(t("noise.mode_" + str(mode)), action("noise", "write", mode=mode),
                               noise.get("mode") == mode, enabled) for mode in noise["modes"]]
            mode, level = noise.get("mode"), noise.get("level")
            unknown = (mode if mode is not None and mode not in noise["modes"] else
                       level if mode in (1, 2) and level is not None
                       and level not in tuple(value for value, _ in noise.get("levels", ())) else None)
            if unknown is not None:
                children.append(item(str(t("noise.unknown", code=unknown)), None, enabled=False))
            feedback("noise", noise, children)
            group(t("noise.title"), children)
            group(t("noise.level"), [
                choice(label, action("noise", "write", mode=noise.get("mode"), level=level),
                       noise.get("level") == level, enabled)
                for level, label in noise.get("levels", ())])

        if state.get("latency_available"):
            latency = state.get("latency", {})
            mode = latency.get("mode", "off")
            label = (t("tray.auto") if mode == "auto" else
                     t("latency.unknown") if latency.get("enabled") is None else
                     t("tray.on" if latency["enabled"] else "tray.off"))
            entries.append(item(str(label), action("latency", "toggle"),
                                checked=lambda entry: latency.get("enabled") is True,
                                enabled=connected))
        entries.extend([separator, item(str(t("tray.quit")), lambda icon, entry: self._exit())])
        return pystray.Menu(*entries)

    def refresh_menu(self) -> None:
        """Refresh tray menu to reflect updated checked states."""
        icon = self.icon
        if self.available and icon:
            try:
                icon.title = self._tooltip()
            except Exception as error:
                print(f"Tray tooltip update unavailable: {error}")
        if self.available and icon and getattr(type(icon), "HAS_MENU", False):
            try:
                icon.menu = self._build_menu()
                icon.update_menu()
            except Exception as error:
                print(f"Tray menu update unavailable: {error}")

    def set_device(self, name: str, image_path: str = "") -> None:
        """Share the screen's local device presentation with notifications.

        Keep the last known device across the empty catalog update on disconnect
        so a reconnect can use its cached picture without waiting for the API.
        """
        if name or image_path:
            with self._device_lock:
                self._device = (name or "Redmi Buds 6 Play", image_path)

    def notify(self, message: str, title: str = "Mi Buds Client", *, device: bool = False,
               silent: bool = True) -> None:
        """Show notifications silently by default, including text fallback."""
        if self._stopped.is_set():
            return

        image_path = ""
        if device:
            with self._device_lock:
                title, image_path = self._device
        # Capture the active language now, including asynchronous Linux delivery.
        text = render(message)
        if self._linux_notifications is not None:
            self._linux_notifications.notify(text, title, image_path, silent=silent,
                                             action_label=str(t("tray.open")))
            return
        icon = self.icon
        if not self.available or not icon:
            return

        def plain():
            if silent:
                # Never fall back to pystray.notify(): it has no sound control.
                # Retry without the picture, preserving silence even on errors.
                def unavailable():
                    print("Silent notification unavailable on this tray backend")

                if not self._image_notifications.show(icon, text, title, "", unavailable, silent=True):
                    unavailable()
                return
            try:
                if hasattr(icon, "notify"):
                    icon.notify(text, title)
            except Exception as e:
                print(f"Tray notify error: {e}")

        if image_path and self._image_notifications.show(icon, text, title, image_path, plain, silent=silent):
            return
        plain()
    
    def _exit(self) -> None:
        """Request application cleanup outside the native tray callback."""
        self.on_exit()

    def stop(self) -> None:
        """Stop the native loop; run() releases notification resources."""
        self._stopped.set()
        self._ready.clear()
        if self._host_monitor:
            self._host_monitor.stop()
        if self._linux_notifications is not None:
            self._linux_notifications.close()
        icon = self.icon
        if icon:
            try:
                icon.stop()
            except Exception as error:
                print(f"Tray stop error: {error}")
