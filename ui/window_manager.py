"""Window Management Module."""

import os
import flet as ft
import subprocess
import threading
import time

class WindowManager:
    """Handles window visibility and events."""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self._is_closing = False
        self._close_lock = threading.Lock()
        self._force_exit_armed = False
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
        """Close the application with a guarded, graceful flow."""
        with self._close_lock:
            if self._is_closing:
                return
            self._is_closing = True

        # Arm safety-net early so hidden-window edge cases cannot hang forever.
        self._force_exit_after_delay()

        self.show_closing_screen()
        self._on_close_handler(None)

    def _run_window_async(self, handler, timeout_sec: float = 1.5) -> bool:
        """Run async Flet window API calls from sync handlers."""
        try:
            # Non-blocking: waiting here can deadlock when called on UI loop paths.
            self.page.run_task(handler)
            return True
        except Exception as e:
            print(f"Window async call error: {e}")
            return False

    def _force_exit_after_delay(self, delay_sec: float = 2.0) -> None:
        """Force process exit only if graceful close gets stuck."""
        with self._close_lock:
            if self._force_exit_armed:
                return
            self._force_exit_armed = True

        def _killer() -> None:
            time.sleep(delay_sec)
            if os.name == "nt":
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(os.getpid())])
            else:
                os._exit(0)

        threading.Thread(target=_killer, daemon=True).start()
        
    def _on_close_handler(self, e) -> None:
        """Handle the graceful close request from Flet."""
        if not self._is_closing:
            self.close()
            return

        try:
            self.page.window.prevent_close = False
            self.page.update()

            # Ask desktop window to close first, fallback to destroy if needed.
            closed = self._run_window_async(self.page.window.close)
            if not closed:
                self._run_window_async(self.page.window.destroy)
        except Exception as e:
            print(f"Window close handler error: {e}")
        finally:
            # Keep a delayed force-exit as a safety net for stuck backend threads.
            self._force_exit_after_delay()
        
    def show_closing_screen(self) -> None:
        """Displays a simple closing screen."""
        try:
            self.page.clean()
            self.apply_show()
            self.page.add(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.ProgressRing(width=50, height=50, stroke_width=4),
                            ft.Text(
                                "Application is closing...",
                                size=20,
                                color=ft.Colors.WHITE,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=20,
                    ),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                )
            )
            self.page.update()
        except Exception as e:
            print(f"UI close update error: {e}")
        
    def apply_show(self) -> None:
        """Apply show state to window."""
        self.page.window.visible = True
        self.page.window.minimized = False
        self.page.window.skip_task_bar = False
        self._apply_legacy_props(visible=True, minimized=False, skip_task_bar=False)
        self.page.update()
        self._run_window_async(self.page.window.to_front, timeout_sec=0.5)
    
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
