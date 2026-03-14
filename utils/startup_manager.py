import os
import sys
import platform

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
        return os.path.abspath(sys.argv[0])

def _get_linux_autostart_path():
    """Returns the path to the Linux autostart .desktop file."""
    autostart_dir = os.path.expanduser("~/.config/autostart")
    return os.path.join(autostart_dir, f"{APP_NAME.lower()}.desktop")

def _set_startup_linux(enabled: bool) -> bool:
    """Enable or disable startup on Linux using XDG Autostart."""
    try:
        desktop_file = _get_linux_autostart_path()
        if enabled:
            autostart_dir = os.path.dirname(desktop_file)
            if not os.path.exists(autostart_dir):
                os.makedirs(autostart_dir)
            
            path = get_executable_path()
            content = f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Exec="{path}"
Terminal=false
X-GNOME-Autostart-enabled=true
"""
            with open(desktop_file, "w") as f:
                f.write(content)
        else:
            if os.path.exists(desktop_file):
                os.remove(desktop_file)
        return True
    except Exception as e:
        print(f"Linux startup error: {e}")
        return False

def _set_startup_windows(enabled: bool) -> bool:
    """Enable or disable startup with Windows Registry."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enabled:
            path = get_executable_path()
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{path}"')
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
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
    return os.path.exists(_get_linux_autostart_path())

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
