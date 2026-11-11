"""Idempotent per-user GNOME bridge setup, also usable from a frozen app."""

import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from .resource_manager import get_resource_path
from .wayland import detect_gnome_fullscreen

UUID = "fullscreen@mibudsclient"


def _run(command):
    return subprocess.run(command, capture_output=True, text=True, check=True, timeout=3)


def _extension_list(key):
    value = _run(["gsettings", "get", "org.gnome.shell", key]).stdout.strip()
    if value.startswith("@as "):
        value = value[4:]
    items = ast.literal_eval(value)
    if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
        raise ValueError("Invalid GNOME extension list")
    return items


def _write_file(path, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def ensure_gnome_bridge():
    """Return ready/relogin/disabled/unavailable/not_needed without raising.

    Install and register only our bundled extension. Preserve all other Shell
    preferences and respect a later manual disable. Never install OS packages,
    enable Shell unsafe mode, or restart the desktop session.
    """
    if (not sys.platform.startswith("linux")
            or not (os.getenv("WAYLAND_DISPLAY") or os.getenv("XDG_SESSION_TYPE") == "wayland")):
        return "not_needed"
    desktop = os.getenv("XDG_CURRENT_DESKTOP", "").casefold()
    if not any(name in desktop for name in ("gnome", "zorin", "ubuntu")):
        return "unavailable"
    if shutil.which("gdbus") is None:
        return "unavailable"
    try:
        version = _run(["gnome-shell", "--version"]).stdout
        if not re.search(r"GNOME Shell 46(?:\.|\s|$)", version):
            return "unavailable"
        if _run(["gsettings", "get", "org.gnome.shell", "disable-user-extensions"]).stdout.strip() == "true":
            return "disabled"
        enabled = _extension_list("enabled-extensions")
        if UUID in _extension_list("disabled-extensions"):
            return "disabled"
        root = os.getenv("XDG_DATA_HOME", "")
        root = Path(root) if os.path.isabs(root) else Path.home() / ".local" / "share"
        target = root / "gnome-shell" / "extensions" / UUID
        marker = target / ".mibuds-setup.json"
        registered = False
        try:
            registered = json.loads(marker.read_text(encoding="utf-8")).get("registered") is True
        except (OSError, ValueError, AttributeError):
            pass
        if registered and UUID not in enabled:
            # The user disabled it after we registered it. Do not undo that.
            return "disabled"

        source = Path(get_resource_path(f"assets/gnome-extension/{UUID}"))
        # Read all bundled files before touching the installed extension.
        files = {name: (source / name).read_bytes() for name in ("extension.js", "metadata.json")}
        existed = (target / "extension.js").exists()
        changed = False
        target.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            destination = target / name
            if not destination.exists() or destination.read_bytes() != content:
                _write_file(destination, content)
                changed = True

        # gnome-extensions can enable a discovered extension immediately. A new
        # extension may be invisible until next login; register it in GSettings
        # too so that login activates it without a terminal command.
        if UUID not in enabled:
            try:
                _run(["gnome-extensions", "enable", UUID])
            except (OSError, subprocess.SubprocessError):
                pass
            enabled = _extension_list("enabled-extensions")
            if UUID not in enabled:
                _run(["gsettings", "set", "org.gnome.shell", "enabled-extensions",
                      repr([*enabled, UUID])])
            if UUID not in _extension_list("enabled-extensions"):
                raise OSError("GNOME did not retain the fullscreen bridge registration")
        if not registered:
            _write_file(marker, b'{"registered": true}\n')
        # Updating files does not replace the JavaScript already in Shell memory.
        if changed and existed:
            return "relogin"
        return "ready" if detect_gnome_fullscreen()[0] is not None else "relogin"
    except (OSError, subprocess.SubprocessError, ValueError, SyntaxError, TypeError) as error:
        print(f"Wayland fullscreen setup unavailable: {error}")
        return "unavailable"
