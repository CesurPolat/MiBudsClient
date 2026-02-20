import os
import sys
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

def set_startup(enabled: bool) -> bool:
    """Enable or disable startup with Windows."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enabled:
            # Use 'pythonw' for script if we want to hide console, 
            # but usually users will have a compiled .exe
            path = get_executable_path()
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{path}"')
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass  # Already disabled
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Startup error: {e}")
        return False

def is_startup_enabled() -> bool:
    """Check if the application is set to run at startup."""
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
