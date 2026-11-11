"""Select a compatible Linux backend before importing pystray."""

import os
import sys
import importlib


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
    """Accept both indicator namespaces supported by pystray."""
    if not _ensure_gi_module():
        return False

    import gi
    for namespace in ("AppIndicator3", "AyatanaAppIndicator3"):
        try:
            gi.require_version(namespace, "0.1")
            importlib.import_module(f"gi.repository.{namespace}")
            return True
        except Exception:
            continue
    return False


def _has_gtk_namespace() -> bool:
    if not _ensure_gi_module():
        return False
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        importlib.import_module("gi.repository.Gtk")
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
        elif _has_gtk_namespace():
            os.environ.setdefault("PYSTRAY_BACKEND", "gtk")


def load_tray_module():
    """Try usable backends without making native tray dependencies fatal."""
    original = os.environ.get("PYSTRAY_BACKEND")
    try:
        if original or not sys.platform.startswith("linux"):
            candidates = [original]
        else:
            candidates = []
            if _has_gtk_namespace():
                if _has_appindicator_namespace():
                    candidates.append("appindicator")
                candidates.append("gtk")
            if os.environ.get("DISPLAY"):
                candidates.append("xorg")
        for backend in candidates:
            if backend:
                os.environ["PYSTRAY_BACKEND"] = backend
            try:
                return importlib.import_module("pystray")
            except Exception as error:
                print(f"Tray backend {backend or 'default'} unavailable: {error}")
        print("System tray unavailable; the application window remains accessible")
        return None
    finally:
        if original is None:
            os.environ.pop("PYSTRAY_BACKEND", None)
        else:
            os.environ["PYSTRAY_BACKEND"] = original
