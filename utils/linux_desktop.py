"""Per-user icon/desktop identity for the Flet Linux client."""

import os
from pathlib import Path
import re
import sys
import tempfile

from .resource_manager import get_resource_path
from .startup_manager import _desktop_argument, _desktop_string

APP_ID = "dev.mibuds.client"
LEGACY_ID = "com.appveyor.flet"
MARKER = "X-MiBudsClient-Managed=true"


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _data_home():
    root = os.getenv("XDG_DATA_HOME", "")
    return Path(root) if os.path.isabs(root) else Path.home() / ".local" / "share"


def _legacy_client():
    # The 0.x prebuilt GTK runner hardcodes com.appveyor.flet. FLET_APP_ID
    # support was added in Flet 1.0; setting it alone cannot fix old clients.
    # The version module is bundled by PyInstaller; dist-info metadata need not
    # be present in a frozen executable.
    from flet_desktop.version import version
    match = re.match(r"(\d+)\.", version)
    if not match:
        raise ValueError("Unknown Flet desktop version")
    return int(match.group(1)) < 1


def setup_linux_desktop():
    """Install a hidden runtime identity entry and return a safe cleanup hook.

    No system files or other applications' desktop entries are overwritten.
    The icon is copied to a persistent user path, never an AppImage mount or a
    PyInstaller extraction directory. Startup's existing single-instance guard
    must run before this function so another launch cannot delete live entries.
    """
    if not sys.platform.startswith("linux"):
        return lambda: None
    os.environ["FLET_APP_ID"] = APP_ID
    owned = []
    try:
        legacy = _legacy_client()
        root = _data_home()
        icon = root / "MiBudsClient" / "icon.png"
        image = Path(get_resource_path("assets/icon.png")).read_bytes()
        if not icon.exists() or icon.read_bytes() != image:
            _write(icon, image)

        appimage = os.getenv("APPIMAGE", "")
        if appimage and os.path.isabs(appimage) and Path(appimage).is_file():
            arguments = [appimage]
        elif getattr(sys, "frozen", False):
            arguments = [sys.executable]
        else:
            arguments = [sys.executable, str(Path(__file__).resolve().parents[1] / "main.py")]
        command = " ".join(_desktop_argument(argument) for argument in arguments)
        data_dirs = os.getenv("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
        for identity in ([APP_ID, LEGACY_ID] if legacy else [APP_ID]):
            target = root / "applications" / f"{identity}.desktop"
            system_entry = any((Path(directory) / "applications" / target.name).exists()
                               for directory in data_dirs if os.path.isabs(directory))
            if system_entry:
                continue
            if target.exists() and MARKER not in target.read_text(encoding="utf-8"):
                continue
            content = ("[Desktop Entry]\nType=Application\nName=MiBudsClient\n"
                       f"Exec={command}\nIcon={_desktop_string(str(icon))}\n"
                       f"StartupWMClass={'flet' if identity == LEGACY_ID else APP_ID}\n"
                       f"NoDisplay=true\nTerminal=false\nCategories=Utility;\n{MARKER}\n")
            encoded = content.encode("utf-8")
            if not target.exists() or target.read_bytes() != encoded:
                _write(target, encoded)
            owned.append((target, encoded))
    except (OSError, ValueError, ImportError) as error:
        print(f"Linux desktop icon registration unavailable: {error}")

    def cleanup():
        for target, expected in owned:
            try:
                # Leave a user/integrator replacement alone, even if the entry
                # was changed while the app was running.
                if target.read_bytes() == expected:
                    target.unlink()
            except FileNotFoundError:
                pass
            except OSError as error:
                print(f"Linux desktop icon cleanup unavailable: {error}")
    return cleanup
