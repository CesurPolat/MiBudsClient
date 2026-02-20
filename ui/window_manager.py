"""Window Management Module."""

import os
import flet as ft
import subprocess
import time

class WindowManager:
    """Handles window visibility and events."""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self._setup_window()
        self._setup_handlers()
    
    def _setup_window(self) -> None:
        """Configure window properties."""
        self.page.window.prevent_close = True
    
    def _setup_handlers(self) -> None:
        """Setup window event handlers."""
        self.page.window.on_event = self._on_window_event_handler
        self.page.on_close = self._on_close_handler
    
    def _on_window_event_handler(self, e) -> None:
        """Handle window events."""
        event_type = getattr(e, "type", None)
        if event_type == ft.WindowEventType.CLOSE:
            if self.page.window.prevent_close:
                self.hide()
    
    def show(self) -> None:
        """Show and bring window to front via pubsub."""
        self.page.pubsub.send_all({"type": "window", "action": "show"})
    
    def hide(self) -> None:
        """Hide window to tray via pubsub."""
        self.page.pubsub.send_all({"type": "window", "action": "hide"})

    def close(self) -> None:
        """Properly close the window with a closing screen."""
        self.show_closing_screen()
        # Simulate some cleanup time, then trigger the actual close
        time.sleep(1) # Give some time for the user to see the closing screen
        self.page.on_close(None) # Trigger the graceful Flet shutdown
        
    def _on_close_handler(self, e) -> None:
        """Handles the graceful closing of the application."""
        print("Application is initiating graceful shutdown...")
        # Perform any cleanup here if necessary before closing
        
        self.page.window.prevent_close = False # Allow the window to be closed
        self.page.window.close() # Close the Flet window
        subprocess.call(['taskkill', '/F', '/T', '/PID', str(os.getpid())])
        
    def show_closing_screen(self) -> None:
        """Displays a simple closing screen."""
        self.page.clean() # Clear all existing controls
        self.apply_show() # Ensure the window is visible to show the closing screen
        self.page.add(
            ft.Container(
                content=ft.Column(
                    [
                        ft.ProgressRing(width=50, height=50, stroke_width=4),
                        ft.Text(
                            "Application is closing...", 
                            size=20, 
                            color=ft.Colors.WHITE
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=20
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )
        )
        self.page.update()
        
    def apply_show(self) -> None:
        """Apply show state to window."""
        self.page.window.visible = True
        self.page.window.minimized = False
        self.page.window.skip_task_bar = False
        self._apply_legacy_props(visible=True, minimized=False, skip_task_bar=False)
        self.page.update()
        self.page.window.to_front()
    
    def apply_hide(self) -> None:
        """Apply hide state to window."""
        self.page.window.minimized = False
        self.page.window.visible = False
        self.page.window.skip_task_bar = True
        self._apply_legacy_props(visible=False, minimized=False, skip_task_bar=True)
        self.page.update()
    
    def _apply_legacy_props(self, visible: bool, minimized: bool, skip_task_bar: bool) -> None:
        """Apply legacy property names for compatibility."""
        try:
            self.page.window_visible = visible
            self.page.window_minimized = minimized
            self.page.window_skip_task_bar = skip_task_bar
        except Exception:
            pass
