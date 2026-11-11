import os
import sys
from pathlib import Path

def get_app_dir() -> Path:
    """
    Returns the directory where the application/executable resides.
    If compiled with PyInstaller, returns the directory of the executable,
    not the temporary extraction directory.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def get_default_vault_file() -> Path:
    """
    Returns the path to the portable encrypted vault file,
    stored directly alongside the executable / application directory.
    """
    return get_app_dir() / "chrome_profile.vault"

def get_chrome_user_data_dir() -> Path:
    """
    Detects the Chrome User Data directory for the current operating system.
    """
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "Google" / "Chrome" / "User Data"
        return Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    else:
        # Linux / Unix
        return Path.home() / ".config" / "google-chrome"
