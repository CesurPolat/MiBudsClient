"""Manually run the same per-user setup used by the application's worker."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.wayland_setup import ensure_gnome_bridge


def main():
    state = ensure_gnome_bridge()
    messages = {
        'ready': 'Wayland game mode support is ready.',
        'relogin': 'Support installed and registered. Log out and back in to activate it; no further command is needed.',
        'not_needed': 'No extension is needed in this desktop session.',
        'disabled': 'GNOME extensions or this bridge were disabled in desktop settings. That preference was preserved.',
        'unavailable': 'Automatic setup is unavailable. Check GNOME version, system tools and user-directory permissions.',
    }
    print(messages[state])


if __name__ == '__main__':
    main()
