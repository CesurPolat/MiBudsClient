"""Window Management Module."""

import os
import asyncio
import math
import struct
import flet as ft
from utils.i18n import t
from utils.window_geometry import fit_window_size, get_work_area_size
from .constants import WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT
import subprocess
import threading
import time

class WindowManager:
    """Handles window visibility and events."""
    
    def __init__(self, page: ft.Page, *, auto_resize: bool = False):
        self.page = page
        self._auto_resize = auto_resize
        self._is_closing = False
        self._session_closed = False
        self._close_lock = threading.Lock()
        self._force_exit_armed = False
        self._fit_revision = 0
        self._content_measurement = None
        self._work_area = get_work_area_size() if auto_resize else None
        self._setup_window()
        self._setup_handlers()
    
    def _setup_window(self) -> None:
        """Configure window properties."""
        self.page.window.prevent_close = True
        if not self._auto_resize:
            self.page.window.width = WINDOW_WIDTH
            self.page.window.height = WINDOW_HEIGHT
            self.page.window.min_width = WINDOW_WIDTH
            self.page.window.min_height = WINDOW_HEIGHT
            self.page.window.max_width = WINDOW_WIDTH
            self.page.window.max_height = WINDOW_HEIGHT
            self.page.window.resizable = self.page.platform != ft.PagePlatform.WINDOWS
            self.page.window.maximizable = False
            return
        width, height, min_width, min_height = fit_window_size(
            (WINDOW_WIDTH, WINDOW_HEIGHT),
            (WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT), self._work_area,
        )
        self.page.window.width = width
        self.page.window.height = height
        self.page.window.min_width = min_width
        self.page.window.min_height = min_height
        self.page.window.max_width = None
        self.page.window.max_height = None
        self.page.window.resizable = True
        self.page.window.maximizable = True
    
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

    def set_content_measurement(self, measurement: ft.Screenshot) -> None:
        self._content_measurement = measurement
        self.request_content_fit()

    def request_content_fit(self) -> None:
        """Coalesce layout changes and fit alongside the screen transition."""
        if (self._auto_resize and self._content_measurement is not None
                and not self._is_closing):
            self._fit_revision += 1
            self.page.run_task(self._fit_content_after_layout, self._fit_revision)

    async def _fit_content_after_layout(self, revision: int) -> None:
        await asyncio.sleep(0.04)
        window = self.page.window
        if (revision != self._fit_revision or self._is_closing
                or window.maximized or window.minimized or window.full_screen
                or not window.visible):
            return
        try:
            # Flet has no control-size query. Capture only this shrink-wrapped
            # Column at 1x and read PNG dimensions in memory; no image is saved.
            png = await self._content_measurement.capture(pixel_ratio=1.0)
            if revision != self._fit_revision or self._is_closing:
                return
            if png[:8] != b"\x89PNG\r\n\x1a\n":
                return
            content_height = struct.unpack(">I", png[20:24])[0]
            if not self.page.height or not window.height:
                return
            frame_height = max(0, window.height - self.page.height)
            target = math.ceil(content_height + 40 + frame_height)
            _, target, _, _ = fit_window_size(
                (window.width, target), (WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT),
                self._work_area,
            )
            if abs(window.height - target) > 1:
                await self._animate_height(target, revision)
        except Exception as error:
            print(f"Content size measurement unavailable: {error}")

    async def _animate_height(self, target: int, revision: int) -> None:
        """Ease the native window to its content height without blocking Flet."""
        window = self.page.window
        initial_height = window.height
        started = time.monotonic()
        duration = 0.28
        while True:
            # A newer layout takes over from the current interpolated height.
            if (revision != self._fit_revision or self._is_closing
                    or window.maximized or window.minimized or window.full_screen
                    or not window.visible):
                return
            progress = min(1.0, (time.monotonic() - started) / duration)
            eased = (4 * progress ** 3 if progress < 0.5
                     else 1 - (-2 * progress + 2) ** 3 / 2)
            height = round(initial_height + (target - initial_height) * eased)
            if height != window.height:
                window.height = height
                self.page.update()
            if progress >= 1:
                return
            await asyncio.sleep(1 / 60)
    
    def show(self) -> None:
        """Show and bring window to front via pubsub."""
        if self._is_closing or self._session_closed:
            return
        self.page.pubsub.send_all({"type": "window", "action": "show"})
    
    def hide(self) -> None:
        """Hide window to tray via pubsub."""
        if self._is_closing or self._session_closed:
            return
        self.page.pubsub.send_all({"type": "window", "action": "hide"})

    def close(self) -> None:
        """Close the application with a guarded, graceful flow."""
        with self._close_lock:
            if self._is_closing or self._session_closed:
                return
            self._is_closing = True

        # Arm safety-net early so hidden-window edge cases cannot hang forever.
        self._force_exit_after_delay()

        self.show_closing_screen()
        self._run_window_async(self._close_window)

    def _run_window_async(self, handler, timeout_sec: float = 1.5) -> bool:
        """Run async Flet window API calls from sync handlers."""
        if self._session_closed:
            return False

        async def guarded():
            if self._session_closed or (self._is_closing and handler != self._close_window):
                return
            try:
                await asyncio.wait_for(handler(), timeout=timeout_sec)
            except Exception as error:
                if not self._ignore_destroyed_session(error):
                    print(f"Window async call error: {error}")

        try:
            # Non-blocking: waiting here can deadlock when called on UI loop paths.
            # Catch inside the coroutine: run_task re-raises failed Future results.
            self.page.run_task(guarded)
            return True
        except Exception as e:
            if not self._ignore_destroyed_session(e):
                print(f"Window async call error: {e}")
            return False

    def _ignore_destroyed_session(self, error) -> bool:
        if (isinstance(error, RuntimeError)
                and str(error) == "An attempt to fetch destroyed session."):
            self._session_closed = True
            return True
        return False

    async def _close_window(self) -> None:
        if self._session_closed:
            return
        try:
            self.page.window.prevent_close = False
            self.page.update()
            await asyncio.wait_for(self.page.window.close(), timeout=1.0)
        except Exception as error:
            if self._ignore_destroyed_session(error) or self._session_closed:
                return
            print(f"Window close failed, trying destroy: {error}")
            await self.page.window.destroy()

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
        """Flet emits on_close after destroying the session, not as a request."""
        with self._close_lock:
            self._session_closed = True
            self._is_closing = True
        # No UI updates or window RPCs are valid at this point.
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
                                t("app.closing"),
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
        if self._session_closed:
            return
        self.page.window.visible = True
        self.page.window.minimized = False
        self.page.window.skip_task_bar = False
        self._apply_legacy_props(visible=True, minimized=False, skip_task_bar=False)
        self.page.update()
        self._run_window_async(self.page.window.to_front, timeout_sec=0.5)
    
    def apply_hide(self) -> None:
        """Apply hide state to window."""
        if self._session_closed or self._is_closing:
            return
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
