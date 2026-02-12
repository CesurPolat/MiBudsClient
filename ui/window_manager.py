"""Window Management Module."""

import flet as ft


class WindowManager:
    """Handles window visibility and events."""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self._setup_window()
        self._setup_handlers()
    
    def _setup_window(self) -> None:
        """Configure window properties."""
        self.page.window.prevent_close = True
        try:
            self.page.window_prevent_close = True
        except Exception:
            pass
    
    def _setup_handlers(self) -> None:
        """Setup window event handlers."""
        self.page.window.on_event = self._on_window_event
        self.page.on_close = lambda e: self.hide()
    
    def _on_window_event(self, e) -> None:
        """Handle window events."""
        event_type = getattr(e, "type", None)
        if event_type == ft.WindowEventType.CLOSE:
            self.hide()
    
    def show(self) -> None:
        """Show and bring window to front via pubsub."""
        self.page.pubsub.send_all({"type": "window", "action": "show"})
    
    def hide(self) -> None:
        """Hide window to tray via pubsub."""
        self.page.pubsub.send_all({"type": "window", "action": "hide"})
    
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
