"""Select a compatible Linux backend before importing pystray."""

import os
import sys


def _ensure_gi_module() -> bool:
    try:
        import gi  # type: ignore  # noqa: F401
        return True
    except Exception:
        pass

    # Ubuntu'da gi modulu cogu zaman sistem dist-packages altindadir.
    for path in (
        "/usr/lib/python3/dist-packages",
        "/usr/lib/x86_64-linux-gnu/python3/dist-packages",
    ):
        if os.path.isdir(path) and path not in sys.path:
            sys.path.append(path)

    try:
        import gi  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False

def _has_appindicator_namespace() -> bool:
    """Check whether gi exposes AppIndicator3 required by pystray appindicator backend."""
    if not _ensure_gi_module():
        return False

    try:
        import gi
        gi.require_version("AppIndicator3", "0.1")
        return True
    except Exception:
        return False


def configure_tray_backend() -> None:
    """Respect an explicit backend and select an available Linux backend."""
    if sys.platform.startswith("linux"):
        # Prefer appindicator only when the required namespace is available.
        # Otherwise force gtk to avoid ValueError: Namespace AppIndicator3 not available.
        if _has_appindicator_namespace():
            os.environ.setdefault("PYSTRAY_BACKEND", "appindicator")
        elif _ensure_gi_module():
            os.environ.setdefault("PYSTRAY_BACKEND", "gtk")
