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
        on_latency_toggle: Optional[Callable[[bool], None]] = None,
        get_latency_state: Optional[Callable[[], bool]] = None
    ):
        self.on_show = on_show
        self.on_exit = on_exit
        self.on_latency_toggle = on_latency_toggle
        self.get_latency_state = get_latency_state
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
                        "Low Latency Mode",
                        self._on_toggle,
                        checked=lambda item: self._get_state()
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
    
    def _get_state(self) -> bool:
        """Get current latency state."""
        if self.get_latency_state:
            return self.get_latency_state()
        return False

    def _on_toggle(self, icon, item) -> None:
        """Toggle latency mode."""
        if self.on_latency_toggle:
            new_state = not self._get_state()
            self.on_latency_toggle(new_state)

    def refresh_menu(self) -> None:
        """Refresh tray menu to reflect updated checked states."""
        if self.icon and getattr(pystray.Icon, "HAS_MENU", False):
            self.icon.update_menu()
    
    def _exit(self) -> None:
        """Stop tray and exit application."""
        if self.icon:
            self.icon.stop()
        self.on_exit()