"""Cross-platform fullscreen detector for auto low-latency switching."""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from typing import Callable, Optional


class FullscreenGameMonitor:
    """Poll foreground fullscreen state and notify on stable transitions."""

    def __init__(
        self,
        on_fullscreen_change: Callable[[bool, str], None],
        on_log: Optional[Callable[[str], None]] = None,
        poll_interval: float = 1.5,
        stable_polls: int = 2,
    ):
        self._on_fullscreen_change = on_fullscreen_change
        self._on_log = on_log
        self._poll_interval = poll_interval
        self._stable_polls = max(1, stable_polls)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_state = False
        self._last_raw_state: Optional[bool] = None
        self._stable_count = 0
        self._unsupported_logged = False
        self._last_app_id = ""

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run_loop(self) -> None:
        while self._running:
            raw_state, app_id = self._detect_fullscreen_state()
            if raw_state is None:
                if not self._unsupported_logged:
                    self._unsupported_logged = True
                    self._log("Fullscreen detection unavailable on this desktop session.")
                time.sleep(self._poll_interval)
                continue

            self._unsupported_logged = False
            if raw_state == self._last_raw_state:
                self._stable_count += 1
            else:
                self._last_raw_state = raw_state
                self._stable_count = 1

            if self._stable_count >= self._stable_polls and raw_state != self._current_state:
                self._current_state = raw_state
                self._last_app_id = app_id
                self._on_fullscreen_change(raw_state, app_id)

            time.sleep(self._poll_interval)

    def _detect_fullscreen_state(self) -> tuple[Optional[bool], str]:
        if os.name == "nt":
            return self._detect_windows_fullscreen()

        if sys_platform_startswith("linux"):
            return self._detect_linux_fullscreen()

        return None, ""

    def _detect_windows_fullscreen(self) -> tuple[Optional[bool], str]:
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            def _foreground_process_name(hwnd) -> str:
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if not pid.value:
                    return ""

                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
                )
                if not handle:
                    return ""

                try:
                    buffer_len = wintypes.DWORD(1024)
                    buffer = ctypes.create_unicode_buffer(buffer_len.value)
                    ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(
                        handle, 0, buffer, ctypes.byref(buffer_len)
                    )
                    if not ok:
                        return ""
                    return os.path.basename(buffer.value).lower()
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)

            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return False, ""

            app_id = _foreground_process_name(hwnd)

            if user32.IsIconic(hwnd):
                return False, app_id

            rect = RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return False, app_id

            monitor = user32.MonitorFromWindow(hwnd, 2)
            if not monitor:
                return False, app_id

            monitor_info = MONITORINFO()
            monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
            if not user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)):
                return False, app_id

            tolerance = 2
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            monitor_width = monitor_info.rcMonitor.right - monitor_info.rcMonitor.left
            monitor_height = monitor_info.rcMonitor.bottom - monitor_info.rcMonitor.top

            if width <= 0 or height <= 0:
                return False, app_id

            is_fullscreen = (
                abs(rect.left - monitor_info.rcMonitor.left) <= tolerance
                and abs(rect.top - monitor_info.rcMonitor.top) <= tolerance
                and abs(width - monitor_width) <= tolerance
                and abs(height - monitor_height) <= tolerance
            )
            return is_fullscreen, app_id
        except Exception as e:
            self._log(f"Windows fullscreen detection error: {e}")
            return None, ""

    def _detect_linux_fullscreen(self) -> tuple[Optional[bool], str]:
        # Wayland sessions commonly hide this info from xprop/xwininfo.
        if os.getenv("WAYLAND_DISPLAY"):
            return None, ""

        try:
            active = subprocess.run(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                capture_output=True,
                text=True,
                check=False,
            )
            line = active.stdout.strip()
            match = re.search(r"(0x[0-9a-fA-F]+)$", line)
            if not match:
                return False, ""

            win_id = match.group(1)
            if win_id == "0x0":
                return False, ""

            wm_class = subprocess.run(
                ["xprop", "-id", win_id, "WM_CLASS"],
                capture_output=True,
                text=True,
                check=False,
            )
            app_id = _extract_wm_class(wm_class.stdout)

            wininfo = subprocess.run(
                ["xwininfo", "-id", win_id],
                capture_output=True,
                text=True,
                check=False,
            )
            if wininfo.returncode != 0:
                return None, app_id

            x = _extract_int(wininfo.stdout, r"Absolute upper-left X:\s+(-?\d+)")
            y = _extract_int(wininfo.stdout, r"Absolute upper-left Y:\s+(-?\d+)")
            width = _extract_int(wininfo.stdout, r"Width:\s+(\d+)")
            height = _extract_int(wininfo.stdout, r"Height:\s+(\d+)")
            if None in (x, y, width, height):
                return None, app_id

            screen = subprocess.run(
                ["xrandr", "--current"],
                capture_output=True,
                text=True,
                check=False,
            )
            if screen.returncode != 0:
                return None, app_id

            sm = re.search(r"(\d+)x(\d+)\s+\d+\.\d+\*", screen.stdout)
            if not sm:
                sm = re.search(r"current\s+(\d+)\s+x\s+(\d+)", screen.stdout)
            if not sm:
                return None, app_id

            screen_w = int(sm.group(1))
            screen_h = int(sm.group(2))
            tolerance = 4
            is_fullscreen = (
                abs(x) <= tolerance
                and abs(y) <= tolerance
                and abs(width - screen_w) <= tolerance
                and abs(height - screen_h) <= tolerance
            )
            return is_fullscreen, app_id
        except FileNotFoundError:
            return None, ""
        except Exception as e:
            self._log(f"Linux fullscreen detection error: {e}")
            return None, ""

    def _log(self, message: str) -> None:
        if self._on_log:
            self._on_log(message)


def _extract_int(text: str, pattern: str) -> Optional[int]:
    match = re.search(pattern, text)
    if not match:
        return None
    return int(match.group(1))


def _extract_wm_class(output: str) -> str:
    if "=" not in output:
        return ""

    _, raw = output.split("=", 1)
    parts = [segment.strip().strip('"').lower() for segment in raw.split(",")]
    parts = [segment for segment in parts if segment]
    if not parts:
        return ""
    return parts[-1]


def sys_platform_startswith(prefix: str) -> bool:
    return os.sys.platform.startswith(prefix)
