"""Read foreground state from the optional MiBuds GNOME Shell bridge."""

import ast
import json
import os
from pathlib import Path
import subprocess


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
        app_id = state.get("app_id", "")
        if not isinstance(app_id, str):
            return None, ""
        # Prefer the executable name so include/exclude and process-hold rules
        # use the same identity as Linux's pgrep process lookup.
        pid = state.get("pid")
        if type(pid) is int and pid > 0:
            try:
                executable = os.readlink(f"/proc/{pid}/exe")
                app_id = Path(executable.removesuffix(" (deleted)")).name
            except OSError:
                pass
        return state["fullscreen"], app_id.strip().lower()
    except (OSError, subprocess.SubprocessError, ValueError, SyntaxError, TypeError):
        return None, ""
