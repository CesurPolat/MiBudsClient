"""Best-effort desktop work area detection without additional dependencies."""

import os
import re
import subprocess
import sys


def get_work_area_size() -> tuple[int, int] | None:
    """Return logical desktop pixels; let the window manager handle unknown displays."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            rect = wintypes.RECT()
            # SPI_GETWORKAREA excludes the taskbar and follows process DPI scaling.
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                return rect.right - rect.left, rect.bottom - rect.top
        elif sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
            # EWMH exposes the work area for each virtual desktop on X11.
            result = subprocess.run(
                ["xprop", "-root", "_NET_CURRENT_DESKTOP", "_NET_WORKAREA"],
                capture_output=True, text=True, timeout=1, check=True,
            )
            desktop = 0
            areas = []
            for line in result.stdout.splitlines():
                if "=" not in line:
                    continue
                name, values = line.split("=", 1)
                numbers = [int(value) for value in re.findall(r"-?\d+", values)]
                if name.startswith("_NET_CURRENT_DESKTOP") and numbers:
                    desktop = numbers[0]
                elif name.startswith("_NET_WORKAREA"):
                    areas = numbers
            index = desktop * 4
            if index >= 0 and len(areas) >= index + 4:
                width, height = areas[index + 2:index + 4]
                if width > 0 and height > 0:
                    return width, height
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def fit_window_size(
    size: tuple[int, int],
    minimum: tuple[int, int],
    work_area: tuple[int, int] | None,
) -> tuple[int, int, int, int]:
    """Clamp saved dimensions, allowing smaller minimums on small desktops."""
    minimum_width, minimum_height = minimum
    if work_area:
        available_width = max(1, work_area[0] - 24)
        available_height = max(1, work_area[1] - 24)
        minimum_width = min(minimum_width, available_width)
        minimum_height = min(minimum_height, available_height)
        width = min(max(size[0], minimum_width), available_width)
        height = min(max(size[1], minimum_height), available_height)
    else:
        width = max(size[0], minimum_width)
        height = max(size[1], minimum_height)
    return width, height, minimum_width, minimum_height
