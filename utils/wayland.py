"""Read foreground state through each Wayland compositor's own interfaces."""

import ast
import json
import os
from pathlib import Path
import subprocess

from .resource_manager import get_resource_path


def compositor():
    """Select one backend; never substitute XWayland for the active desktop."""
    desktop = set(os.getenv("XDG_CURRENT_DESKTOP", "").casefold().split(":"))
    if "hyprland" in desktop or os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
        return "hyprland"
    if "sway" in desktop or os.getenv("SWAYSOCK"):
        return "sway"
    if desktop.intersection({"kde", "plasma"}):
        return "kde"
    if desktop.intersection({"gnome", "zorin", "ubuntu"}):
        return "gnome"
    return ""


def _app_identity(app_id, pid):
    if not isinstance(app_id, str):
        raise ValueError("Invalid application identity")
    if type(pid) is int and pid > 0:
        try:
            app_id = Path(os.readlink(f"/proc/{pid}/exe").removesuffix(" (deleted)")).name
        except OSError:
            pass
    return app_id.strip().lower()


def _query_json(command):
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=1.5)
    return json.loads(result.stdout)


def detect_sway_fullscreen():
    try:
        tree = _query_json(["swaymsg", "-r", "-t", "get_tree"])
        if not isinstance(tree, dict) or tree.get("type") != "root":
            return None, ""
        pending = [(tree, False)]
        while pending:
            node, ancestor_fullscreen = pending.pop()
            if not isinstance(node, dict):
                raise ValueError("Invalid Sway node")
            mode = node.get("fullscreen_mode", 0)
            if type(mode) is not int or mode not in (0, 1, 2):
                raise ValueError("Invalid Sway fullscreen state")
            fullscreen = ancestor_fullscreen or mode != 0
            properties = node.get("window_properties") or {}
            if not isinstance(properties, dict):
                raise ValueError("Invalid Sway window properties")
            app_id = node.get("app_id") or properties.get("class") or ""
            if node.get("focused") is True and (app_id or node.get("pid")):
                return fullscreen, _app_identity(app_id, node.get("pid"))
            for field in ("nodes", "floating_nodes"):
                children = node.get(field, [])
                if not isinstance(children, list):
                    raise ValueError("Invalid Sway children")
                pending.extend((child, fullscreen) for child in children)
        return False, ""
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return None, ""


def detect_hyprland_fullscreen():
    try:
        window = _query_json(["hyprctl", "-j", "activewindow"])
        if not isinstance(window, dict):
            return None, ""
        if not window:
            return False, ""
        mode = window.get("fullscreen")
        if type(mode) is bool:  # Older Hyprland versions used a boolean.
            fullscreen = mode
        elif type(mode) is int and mode in (0, 1, 2, 3):
            fullscreen = bool(mode & 2)  # 1 is maximized, not fullscreen.
        else:
            return None, ""
        return fullscreen, _app_identity(window.get("class", ""), window.get("pid"))
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return None, ""


def detect_kde_fullscreen():
    try:
        # kdotool handles loading/running/removing the read-only KWin query.
        state = _query_json(["kdotool", "kwinscript", "--file",
                             get_resource_path("assets/kwin/fullscreen.js")])
        if (not isinstance(state, dict) or state.get("available") is not True
                or type(state.get("fullscreen")) is not bool):
            return None, ""
        return state["fullscreen"], _app_identity(state.get("app_id", ""), state.get("pid"))
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return None, ""


def detect_wayland_fullscreen():
    backend = {"gnome": detect_gnome_fullscreen, "kde": detect_kde_fullscreen,
               "sway": detect_sway_fullscreen, "hyprland": detect_hyprland_fullscreen}.get(compositor())
    return backend() if backend else (None, "")


def detect_gnome_fullscreen():
    """Return unknown if the compositor bridge is missing or unavailable."""
    try:
        result = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
             "--object-path", "/org/mibuds/Fullscreen",
             "--method", "org.mibuds.Fullscreen.GetState", "--timeout", "1"],
            capture_output=True, text=True, check=False, timeout=1.5,
        )
        if result.returncode:
            return None, ""
        # gdbus prints a GVariant tuple containing a single JSON string. Parse
        # its literal representation, never evaluate code from a bus response.
        reply = ast.literal_eval(result.stdout.strip())
        if not isinstance(reply, tuple) or len(reply) != 1 or not isinstance(reply[0], str):
            return None, ""
        state = json.loads(reply[0])
        if (not isinstance(state, dict) or state.get("version") != 1
                or state.get("available") is not True
                or type(state.get("fullscreen")) is not bool):
            return None, ""
        # Prefer the executable name so include/exclude and process-hold rules
        # use the same identity as Linux's pgrep process lookup.
        return state["fullscreen"], _app_identity(state.get("app_id", ""), state.get("pid"))
    except (OSError, subprocess.SubprocessError, ValueError, SyntaxError, TypeError):
        return None, ""
