"""Install the bundled GNOME 46 fullscreen bridge for the current user."""

from pathlib import Path
import os
import re
import shutil
import subprocess
import sys

UUID = 'fullscreen@mibudsclient'


def main():
    if not sys.platform.startswith('linux'):
        raise SystemExit('This helper requires Linux with GNOME Shell 46.')
    try:
        result = subprocess.run(['gnome-shell', '--version'], capture_output=True,
                                text=True, check=True, timeout=3)
    except (OSError, subprocess.SubprocessError) as error:
        raise SystemExit(f'Could not determine GNOME Shell version: {error}')
    if not re.search(r'GNOME Shell 46(?:\.|\s|$)', result.stdout):
        raise SystemExit('The bundled bridge currently targets GNOME Shell 46.')
    source = Path(__file__).resolve().parents[1] / 'assets' / 'gnome-extension' / UUID
    root = os.environ.get('XDG_DATA_HOME', '')
    root = Path(root) if os.path.isabs(root) else Path.home() / '.local' / 'share'
    destination = root / 'gnome-shell' / 'extensions' / UUID
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('metadata.json', 'extension.js'):
        shutil.copy2(source / name, destination / name)
    print(f'Installed fullscreen bridge in {destination}')
    try:
        result = subprocess.run(['gnome-extensions', 'enable', UUID],
                                capture_output=True, text=True, timeout=3, check=False)
        if result.returncode == 0:
            print('Bridge enabled. MiBudsClient will detect it automatically.')
            print('If this updates an already loaded bridge, log out and back in to load the new code.')
            return
        print(result.stderr.strip() or result.stdout.strip())
    except (OSError, subprocess.SubprocessError) as error:
        print(f'Could not enable bridge in this session: {error}')
    print('Log out and back in, then run:')
    print(f'gnome-extensions enable {UUID}')
    print('MiBudsClient will detect the bridge automatically once it is enabled.')


if __name__ == '__main__':
    main()
