"""System tray icon and menu."""

from typing import Callable, Optional
import threading
from utils.i18n import t, render
from utils.image_notifications import ImageNotifications

from utils.tray_backend import load_tray_module

# pystray chooses its backend during import, so configure it first.
pystray = load_tray_module()

from utils.resource_manager import load_pil_image
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
    ):
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
                menu = pystray.Menu(
                    pystray.MenuItem(lambda item: t("tray.open"), lambda icon, item: self.on_show(), default=True),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem(
                        lambda item: t("tray.off"),
                        lambda icon, item: self._on_mode_select("off"),
                        visible=lambda item: self.latency_available(),
                        checked=lambda item: self._is_mode("off"),
                    ),
                    pystray.MenuItem(
                        lambda item: t("tray.auto"),
                        lambda icon, item: self._on_mode_select("auto"),
                        visible=lambda item: self.latency_available(),
                        checked=lambda item: self._is_mode("auto"),
                    ),
                    pystray.MenuItem(
                        lambda item: t("tray.on"),
                        lambda icon, item: self._on_mode_select("on"),
                        visible=lambda item: self.latency_available(),
                        checked=lambda item: self._is_mode("on"),
                    ),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem(lambda item: t("tray.quit"), lambda icon, item: self._exit())
                )
            else:
                print(
                    f"Tray backend has no menu support: {pystray.Icon.__module__}. "
                    "Open/Quit options in tray menu are unavailable."
                )
                menu = pystray.Menu(
                    pystray.MenuItem(lambda item: t("tray.open"), lambda icon, item: self.on_show(), default=True)
                )
            
            self.icon = pystray.Icon("MiBudsClient", tray_image, "Mi Buds Client", menu)
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
                        self._ready.set()
                    except Exception as error:
                        print(f"Tray icon unavailable: {error}")
                        self.on_show()
                        icon.stop()

            self.icon.run(setup=setup)
        except Exception as e:
            print(f"Tray error: {e}")
        finally:
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

    def refresh_menu(self) -> None:
        """Refresh tray menu to reflect updated checked states."""
        icon = self.icon
        if self.available and icon and getattr(type(icon), "HAS_MENU", False):
            try:
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
        icon = self.icon
        if not self.available or not icon:
            return

        image_path = ""
        if device:
            with self._device_lock:
                title, image_path = self._device
        # Capture the active language now, including asynchronous Linux delivery.
        text = render(message)

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
        icon = self.icon
        if icon:
            try:
                icon.stop()
            except Exception as error:
                print(f"Tray stop error: {error}")
