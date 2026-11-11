import os
import sys
import platform
import subprocess
import configparser
import io
import tempfile

if platform.system() == "Windows":
    import winreg

APP_NAME = "MiBudsClient"

def get_executable_path():
    """Returns the path to the executable or script."""
    if getattr(sys, 'frozen', False):
        # Running as compiled .exe (PyInstaller)
        return sys.executable
    else:
        # Running as python script
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")


def _startup_arguments():
    path = get_executable_path()
    return [path] if getattr(sys, "frozen", False) else [sys.executable, path]


def _desktop_string(value):
    return (value.replace("\\", "\\\\").replace("\n", "\\n")
            .replace("\r", "\\r").replace("\t", "\\t"))


def _desktop_argument(value):
    # Exec quoting is separate from the desktop file's string escaping.
    if any(character in value for character in "\n\r\0"):
        raise ValueError("Unsupported control character in startup path")
    escaped = "".join("\\" + character if character in '\\"`$' else character
                      for character in value)
    return '"' + _desktop_string(escaped.replace("%", "%%")) + '"'

def _get_linux_autostart_path():
    """Returns the path to the Linux autostart .desktop file."""
    config_home = os.environ.get("XDG_CONFIG_HOME", "")
    if not os.path.isabs(config_home):
        config_home = os.path.expanduser("~/.config")
    autostart_dir = os.path.join(config_home, "autostart")
    return os.path.join(autostart_dir, f"{APP_NAME.lower()}.desktop")


def _linux_startup_fields():
    return {
        "Type": "Application",
        "Name": APP_NAME,
        "Exec": " ".join(_desktop_argument(argument) for argument in _startup_arguments()),
        "Path": _desktop_string(os.path.dirname(get_executable_path())),
        "Terminal": "false",
        "X-GNOME-Autostart-enabled": "true",
    }


def _write_desktop_file(path, content):
    """Replace a registration atomically so failed repairs keep the old file."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=os.path.dirname(path), delete=False) as output:
            temporary = output.name
            output.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.remove(temporary)

def _set_startup_linux(enabled: bool) -> bool:
    """Enable or disable startup on Linux using XDG Autostart."""
    try:
        desktop_file = _get_linux_autostart_path()
        if enabled:
            autostart_dir = os.path.dirname(desktop_file)
            os.makedirs(autostart_dir, exist_ok=True)
            
            content = "[Desktop Entry]\n" + "".join(
                f"{key}={value}\n" for key, value in _linux_startup_fields().items()
            )
            _write_desktop_file(desktop_file, content)
        else:
            if os.path.exists(desktop_file):
                os.remove(desktop_file)
        
        print(f"Linux startup {'enabled' if enabled else 'disabled'} successfully.")
        print(f"Desktop file path: {desktop_file}")

        return True
    except Exception as e:
        print(f"Linux startup error: {e}")
        return False

def _set_startup_windows(enabled: bool) -> bool:
    """Enable or disable startup with Windows Registry."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                command = subprocess.list2cmdline(_startup_arguments())
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print(f"Windows startup error: {e}")
        return False

def set_startup(enabled: bool) -> bool:
    """Enable or disable startup based on platform."""
    if platform.system() == "Windows":
        return _set_startup_windows(enabled)
    elif platform.system() == "Linux":
        return _set_startup_linux(enabled)
    return False

def _is_startup_enabled_linux() -> bool:
    """Check if startup is enabled on Linux."""
    try:
        entry = configparser.ConfigParser(interpolation=None)
        entry.read(_get_linux_autostart_path(), encoding="utf-8")
        section = entry["Desktop Entry"]
        return (section.get("Type") == "Application"
                and bool(section.get("Exec", "").strip())
                and not section.getboolean("Hidden", fallback=False)
                and section.getboolean("X-GNOME-Autostart-enabled", fallback=True))
    except (OSError, ValueError, KeyError, configparser.Error):
        return False

def _is_startup_enabled_windows() -> bool:
    """Check if startup is enabled on Windows."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False

def is_startup_enabled() -> bool:
    """Check if the application is set to run at startup."""
    if platform.system() == "Windows":
        return _is_startup_enabled_windows()
    elif platform.system() == "Linux":
        return _is_startup_enabled_linux()
    return False


def reconcile_startup() -> bool:
    """Repair an existing enabled registration; never create one when absent.

    Checks the saved launch command, not whether a previous login succeeded.
    Disabled desktop entries are left untouched. Repair failures are logged and
    the returned state is read again rather than assuming the write succeeded.
    """
    try:
        if platform.system() == "Linux":
            desktop_file = _get_linux_autostart_path()
            entry = configparser.ConfigParser(interpolation=None)
            entry.optionxform = str
            if not entry.read(desktop_file, encoding="utf-8"):
                return False
            section = entry["Desktop Entry"]
            if (section.getboolean("Hidden", fallback=False)
                    or not section.getboolean("X-GNOME-Autostart-enabled", fallback=True)):
                return False
            expected = _linux_startup_fields()
            if any(section.get(key) != value for key, value in expected.items()):
                # Preserve unrelated desktop settings, including desktop filters.
                section.update(expected)
                output = io.StringIO()
                entry.write(output, space_around_delimiters=False)
                _write_desktop_file(desktop_file, output.getvalue())
                print("Linux startup registration updated for the current application path")
        elif platform.system() == "Windows":
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                    command, value_type = winreg.QueryValueEx(key, APP_NAME)
            except FileNotFoundError:
                return False
            if (command != subprocess.list2cmdline(_startup_arguments())
                    or value_type != winreg.REG_SZ):
                if not _set_startup_windows(True):
                    print("Windows startup registration repair failed")
    except Exception as error:
        print(f"Startup registration check failed: {error}")
    return is_startup_enabled()
