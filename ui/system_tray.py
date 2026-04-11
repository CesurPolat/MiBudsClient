"""System Tray Module."""

import os
import sys
from typing import Callable, Optional

# Linux'ta pystray backend secimi importtan once yapilmalidir.
def _ensure_gi_module() -> bool:
    try:
        import gi  # type: ignore  # noqa: F401
        return True
    except Exception:
        pass

    # Ubuntu'da gi modulu cogu zaman sistem dist-packages altindadir.
    for path in (
        "/usr/lib/python3/dist-packages",
        "/usr/lib/x86_64-linux-gnu/python3/dist-packages",
    ):
        if os.path.isdir(path) and path not in sys.path:
            sys.path.append(path)

    try:
        import gi  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False

def _has_appindicator_namespace() -> bool:
    """Check whether gi exposes AppIndicator3 required by pystray appindicator backend."""
    if not _ensure_gi_module():
        return False

    try:
        import gi
        gi.require_version("AppIndicator3", "0.1")
        return True
    except Exception:
        return False


if sys.platform.startswith("linux"):
    # Prefer appindicator only when the required namespace is available.
    # Otherwise force gtk to avoid ValueError: Namespace AppIndicator3 not available.
    if _has_appindicator_namespace():
        os.environ.setdefault("PYSTRAY_BACKEND", "appindicator")
    elif _ensure_gi_module():
        os.environ.setdefault("PYSTRAY_BACKEND", "gtk")

import pystray

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
    ):
        self.on_show = on_show
        self.on_exit = on_exit
        self.on_latency_mode_select = on_latency_mode_select
        self.get_latency_mode = get_latency_mode
        self.icon = None
    
    def run(self) -> None:
        """Start the system tray icon."""
        try:
            # Tray uses default icon.png
            tray_image = load_pil_image(TRAY_ICON_PATH, TRAY_ICON_SIZE)

            has_menu = bool(getattr(pystray.Icon, "HAS_MENU", False))
            if has_menu:
                menu = pystray.Menu(
                    pystray.MenuItem("Open", lambda icon, item: self.on_show(), default=True),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem(
                        "Low Latency: Off",
                        lambda icon, item: self._on_mode_select("off"),
                        checked=lambda item: self._is_mode("off"),
                    ),
                    pystray.MenuItem(
                        "Low Latency: Auto",
                        lambda icon, item: self._on_mode_select("auto"),
                        checked=lambda item: self._is_mode("auto"),
                    ),
                    pystray.MenuItem(
                        "Low Latency: On",
                        lambda icon, item: self._on_mode_select("on"),
                        checked=lambda item: self._is_mode("on"),
                    ),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("Quit", lambda icon, item: self._exit())
                )
            else:
                print(
                    f"Tray backend has no menu support: {pystray.Icon.__module__}. "
                    "Open/Quit options in tray menu are unavailable."
                )
                menu = pystray.Menu(
                    pystray.MenuItem("Open", lambda icon, item: self.on_show(), default=True)
                )
            
            self.icon = pystray.Icon("MiBudsClient", tray_image, "Mi Buds Client", menu)
            self.icon.run()
        except Exception as e:
            print(f"Tray error: {e}")
    
    def _get_mode(self) -> str:
        """Get current latency mode."""
        if self.get_latency_mode:
            return self.get_latency_mode() or "off"
        return "off"

    def _is_mode(self, mode: str) -> bool:
        return self._get_mode() == mode

    def _on_mode_select(self, mode: str) -> None:
        """Select latency mode from tray menu."""
        if self.on_latency_mode_select:
            self.on_latency_mode_select(mode)

    def refresh_menu(self) -> None:
        """Refresh tray menu to reflect updated checked states."""
        if self.icon and getattr(pystray.Icon, "HAS_MENU", False):
            self.icon.update_menu()

    def notify(self, message: str, title: str = "Mi Buds Client") -> None:
        """Show a system tray notification when supported by backend."""
        if not self.icon:
            return

        try:
            if hasattr(self.icon, "notify"):
                self.icon.notify(message, title)
        except Exception as e:
            print(f"Tray notify error: {e}")
    
    def _exit(self) -> None:
        """Stop tray and exit application."""
        if self.icon:
            self.icon.stop()
        self.on_exit()