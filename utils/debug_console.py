"""Debug console management for runtime logs and uncaught exceptions."""

from __future__ import annotations

import io
import os
import sys
import threading
import traceback
from collections import deque
from typing import Callable, Deque, Optional


class _TeeStream(io.TextIOBase):
    """Write to original stream and debug manager simultaneously."""

    def __init__(self, manager: "DebugConsoleManager", original_stream, stream_name: str):
        self._manager = manager
        self._original_stream = original_stream
        self._stream_name = stream_name

    def write(self, text: str) -> int:
        if not text:
            return 0

        self._manager._append_log(text, self._stream_name)

        try:
            if self._original_stream:
                self._original_stream.write(text)
                self._original_stream.flush()
        except Exception:
            pass

        self._manager._write_to_console(text)
        return len(text)

    def flush(self) -> None:
        try:
            if self._original_stream:
                self._original_stream.flush()
        except Exception:
            pass


class DebugConsoleManager:
    """Provides runtime debug log capture and F12 console toggling."""

    def __init__(self, max_lines: int = 1200):
        self._lock = threading.Lock()
        self._logs: Deque[str] = deque(maxlen=max_lines)
        self._log_callback: Optional[Callable[[str], None]] = None
        self._installed = False

        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        self._orig_excepthook = sys.excepthook
        self._orig_threading_hook = getattr(threading, "excepthook", None)

        self._console_visible = False
        self._console_stream = None
        self._hotkey_thread: Optional[threading.Thread] = None
        self._hotkey_running = False
        self._hotkey_thread_id: Optional[int] = None

    def start_f12_hotkey_listener(self, on_hotkey: Callable[[], None]) -> bool:
        """Start a Windows hotkey listener for F12 as a reliable fallback."""
        if os.name != "nt" or self._hotkey_running:
            return False

        self._hotkey_running = True
        self._hotkey_thread = threading.Thread(
            target=self._hotkey_loop,
            args=(on_hotkey,),
            daemon=True,
        )
        self._hotkey_thread.start()
        return True

    def stop_f12_hotkey_listener(self) -> None:
        """Stop Windows hotkey listener thread."""
        if os.name != "nt" or not self._hotkey_running:
            return

        self._hotkey_running = False
        try:
            import ctypes

            if self._hotkey_thread_id:
                ctypes.windll.user32.PostThreadMessageW(self._hotkey_thread_id, 0x0012, 0, 0)
        except Exception:
            pass

    def install(self, log_callback: Optional[Callable[[str], None]] = None) -> None:
        """Install stream redirection and exception hooks."""
        if self._installed:
            return

        self._log_callback = log_callback
        sys.stdout = _TeeStream(self, self._orig_stdout, "stdout")
        sys.stderr = _TeeStream(self, self._orig_stderr, "stderr")
        sys.excepthook = self._handle_exception

        if hasattr(threading, "excepthook"):
            threading.excepthook = self._handle_thread_exception

        self._installed = True

    def toggle_console(self) -> str:
        """Toggle native console and return one of: opened, closed, failed."""
        if not os.name == "nt":
            return "failed"

        if self._console_visible:
            self._close_windows_console()
            return "closed"

        self._open_windows_console()
        return "opened" if self._console_visible else "failed"

    def get_recent_logs(self, max_lines: int = 400) -> str:
        """Return a compact log snapshot for UI display if needed."""
        with self._lock:
            lines = list(self._logs)[-max_lines:]
        return "".join(lines)

    def _append_log(self, text: str, stream_name: str) -> None:
        """Store logs in memory and optionally notify callback."""
        prefixed = text
        if stream_name == "stderr" and text.strip():
            prefixed = f"[ERR] {text}"

        with self._lock:
            self._logs.append(prefixed)

        if self._log_callback and text.strip():
            try:
                self._log_callback(prefixed)
            except Exception:
                pass

    def _handle_exception(self, exc_type, exc_value, exc_traceback) -> None:
        formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        self._append_log(formatted, "stderr")
        self._write_to_console(formatted)

        if self._orig_excepthook:
            self._orig_excepthook(exc_type, exc_value, exc_traceback)

    def _handle_thread_exception(self, args) -> None:
        self._handle_exception(args.exc_type, args.exc_value, args.exc_traceback)

        if self._orig_threading_hook:
            try:
                self._orig_threading_hook(args)
            except Exception:
                pass

    def _open_windows_console(self) -> None:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32

            # Force a dedicated debug console window even if process is already attached.
            if kernel32.GetConsoleWindow():
                kernel32.FreeConsole()

            if kernel32.AllocConsole() == 0:
                return

            self._console_stream = open(
                "CONOUT$",
                "w",
                encoding="utf-8",
                buffering=1,
                errors="replace",
            )
            self._console_visible = True
            self._console_stream.write("=== Mi Buds Client Debug Console ===\n")

            snapshot = self.get_recent_logs(max_lines=300)
            if snapshot:
                self._console_stream.write(snapshot)
                self._console_stream.flush()
        except Exception:
            self._console_visible = False
            if self._console_stream:
                try:
                    self._console_stream.close()
                except Exception:
                    pass
            self._console_stream = None

    def _hotkey_loop(self, on_hotkey: Callable[[], None]) -> None:
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            self._hotkey_thread_id = int(kernel32.GetCurrentThreadId())

            hotkey_id = 1
            vk_f12 = 0x7B
            wm_hotkey = 0x0312

            if not user32.RegisterHotKey(None, hotkey_id, 0, vk_f12):
                self._hotkey_running = False
                return

            msg = wintypes.MSG()
            try:
                while self._hotkey_running:
                    result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                    if result <= 0:
                        break

                    if msg.message == wm_hotkey and msg.wParam == hotkey_id:
                        try:
                            on_hotkey()
                        except Exception:
                            pass
            finally:
                user32.UnregisterHotKey(None, hotkey_id)
        except Exception:
            pass
        finally:
            self._hotkey_running = False
            self._hotkey_thread_id = None

    def _close_windows_console(self) -> None:
        try:
            import ctypes

            if self._console_stream:
                self._console_stream.flush()
                self._console_stream.close()
            self._console_stream = None
            ctypes.windll.kernel32.FreeConsole()
        except Exception:
            pass
        finally:
            self._console_visible = False

    def _write_to_console(self, text: str) -> None:
        if not self._console_visible or not self._console_stream:
            return
        try:
            self._console_stream.write(text)
            self._console_stream.flush()
        except Exception:
            pass
