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
        on_low_latency: Optional[Callable] = None,
        on_standard: Optional[Callable] = None
    ):
        self.on_show = on_show
        self.on_exit = on_exit
        self.on_low_latency = on_low_latency
        self.on_standard = on_standard
        self.icon = None
    
    def run(self) -> None:
        """Start the system tray icon."""
        try:
            # Tray uses default icon.png
            tray_image = load_pil_image(TRAY_ICON_PATH, TRAY_ICON_SIZE)

            menu = pystray.Menu(
                pystray.MenuItem("Open", lambda icon, item: self.on_show(), default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Low Latency Mode", lambda icon, item: self._on_low_latency()),
                pystray.MenuItem("Standard Mode", lambda icon, item: self._on_standard()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", lambda icon, item: self._exit())
            )
            
            self.icon = pystray.Icon("MiBudsClient", tray_image, "Mi Buds Client", menu)
            self.icon.run()
        except Exception as e:
            print(f"Tray error: {e}")
    
    def _on_low_latency(self) -> None:
        """Activate low latency mode."""
        if self.on_low_latency:
            self.on_low_latency()
    
    def _on_standard(self) -> None:
        """Activate standard mode."""
        if self.on_standard:
            self.on_standard()
    
    def _exit(self) -> None:
        """Stop tray and exit application."""
        if self.icon:
            self.icon.stop()
        self.on_exit()
