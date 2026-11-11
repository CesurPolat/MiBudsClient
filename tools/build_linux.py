"""Build the Linux executable with native tray backends and bounded GTK assets."""

import os
from pathlib import Path
import sys


def main():
    if not sys.platform.startswith("linux"):
        raise SystemExit("Run this builder on Linux.")
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    # Make distro PyGObject visible without overriding the virtualenv packages.
    for directory in (
        "/usr/lib/python3/dist-packages",
        "/usr/lib/x86_64-linux-gnu/python3/dist-packages",
    ):
        if Path(directory).is_dir() and directory not in sys.path:
            sys.path.append(directory)
    try:
        import gi
    except ImportError as error:
        raise SystemExit("Install python3-gi and GTK 3 introspection before building.") from error
    gi.require_version("Gtk", "3.0")

    from flet_cli.cli import main as flet_main

    sys.argv = [
        "flet", "pack", "main.py", "--icon", "assets/icon.ico",
        "--add-data", "assets:assets", "--name", "MiBudsClient",
        "--hidden-import", "optparse", "--yes",
        "--pyinstaller-build-args=--additional-hooks-dir=tools/pyinstaller_hooks",
    ]
    flet_main()


if __name__ == "__main__":
    main()
