"""System Tray Module."""

import pystray
from typing import Callable, Optional

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
    
    def _exit(self) -> None:
        """Stop tray and exit application."""
        if self.icon:
            self.icon.stop()
        self.on_exit()
