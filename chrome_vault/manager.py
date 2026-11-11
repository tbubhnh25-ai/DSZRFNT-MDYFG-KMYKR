import io
import os
import shutil
import tarfile
from pathlib import Path
from typing import List, Callable, Optional, Dict

from chrome_vault.paths import get_chrome_user_data_dir, get_default_vault_file
from chrome_vault.crypto import encrypt_data, decrypt_data, CryptoError

# Files/folders to skip to avoid bloat, caches, locks, and socket files
IGNORED_PATTERNS = {
    "Cache",
    "Code Cache",
    "DawnCache",
    "GPUCache",
    "ShaderCache",
    "GrShaderCache",
    "Crashpad",
    "lockfile",
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
    "RunningChromeVersion",
}

def list_available_profiles(user_data_dir: Optional[Path] = None) -> List[Dict[str, str]]:
    """
    Lists Chrome profiles found in the Chrome User Data directory.
    Returns list of dicts: [{'id': 'Default', 'name': 'Default'}, ...]
    """
    base_dir = user_data_dir or get_chrome_user_data_dir()
    profiles = []

    if not base_dir.exists():
        return profiles

    # Check Default profile
    if (base_dir / "Default").is_dir():
        profiles.append({"id": "Default", "name": "Default (פרופיל ראשי)"})

    # Check numbered profiles (Profile 1, Profile 2, etc.)
    for item in sorted(base_dir.iterdir()):
        if item.is_dir() and item.name.startswith("Profile "):
            profiles.append({"id": item.name, "name": item.name})

    return profiles


def is_chrome_running() -> bool:
    """
    Checks if Google Chrome process is currently running.
    """
    try:
        import subprocess
        if os.name == "nt":
            output = subprocess.check_output(
                ["tasklist", "/fi", "imagename eq chrome.exe"],
                stderr=subprocess.DEVNULL,
                text=True
            )
            return "chrome.exe" in output.lower()
        else:
            output = subprocess.check_output(
                ["pgrep", "-f", "chrome"],
                stderr=subprocess.DEVNULL,
                text=True
            )
            return bool(output.strip())
    except Exception:
        return False


def create_profile_archive(
    profile_id: str = "Default",
    user_data_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[str], None]] = None
) -> bytes:
    """
    Archives the specified profile folder and critical global Chrome configuration
    (such as 'Local State', which stores encryption keys and profile metadata).
    Returns the compressed tar bytes in memory.
    """
    base_dir = user_data_dir or get_chrome_user_data_dir()
    profile_path = base_dir / profile_id

    if not profile_path.exists():
        raise FileNotFoundError(f"תיקיית הפרופיל לא נמצאה: {profile_path}")

    tar_buffer = io.BytesIO()

    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
        # 1. Archive "Local State" if it exists (crucial for master keys / settings)
        local_state = base_dir / "Local State"
        if local_state.exists():
            if progress_callback:
                progress_callback("מוסיף הגדרות כלליות (Local State)...")
            tar.add(str(local_state), arcname="Local State")

        # 2. Archive profile folder recursively, filtering out cache & lock files
        if progress_callback:
            progress_callback(f"אורז את קבצי הפרופיל {profile_id}...")

        def tar_filter(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
            name = Path(tarinfo.name).name
            if name in IGNORED_PATTERNS or name.endswith(".tmp"):
                return None
            return tarinfo

        tar.add(str(profile_path), arcname=profile_id, filter=tar_filter)

    return tar_buffer.getvalue()


def export_profile_to_vault(
    password: str,
    vault_path: Optional[Path] = None,
    profile_id: str = "Default",
    user_data_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Path:
    """
    Backs up a Chrome profile into an encrypted portable vault file.
    No unencrypted data is left behind.
    """
    target_vault = vault_path or get_default_vault_file()

    if progress_callback:
        progress_callback("מתחיל גיבוי נתוני הפרופיל...")

    archive_bytes = create_profile_archive(
        profile_id=profile_id,
        user_data_dir=user_data_dir,
        progress_callback=progress_callback
    )

    if progress_callback:
        progress_callback("מצפין נתונים עם קוד הגישה...")

    encrypted_bytes = encrypt_data(archive_bytes, password)

    if progress_callback:
        progress_callback(f"שומר את הקובץ המוצפן ביישום: {target_vault.name}...")

    # Write atomically
    temp_target = target_vault.with_suffix(".tmp")
    with open(temp_target, "wb") as f:
        f.write(encrypted_bytes)
    temp_target.replace(target_vault)

    if progress_callback:
        progress_callback("הגיבוי הושלם בהצלחה!")

    return target_vault


def restore_profile_from_vault(
    password: str,
    vault_path: Optional[Path] = None,
    user_data_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[str], None]] = None
) -> None:
    """
    Decrypts the portable vault file and extracts the profile directly
    into the computer's Chrome User Data directory.
    """
    target_vault = vault_path or get_default_vault_file()

    if not target_vault.exists():
        raise FileNotFoundError(f"קובץ הכספת לא נמצא במיקום היישום: {target_vault}")

    if progress_callback:
        progress_callback("קורא ומפענח את קובץ הכספת...")

    with open(target_vault, "rb") as f:
        encrypted_bytes = f.read()

    plaintext_archive = decrypt_data(encrypted_bytes, password)

    if progress_callback:
        progress_callback("קוד הגישה אומת בהצלחה! משחזר קבצים למחשב...")

    base_dir = user_data_dir or get_chrome_user_data_dir()
    base_dir.mkdir(parents=True, exist_ok=True)

    tar_buffer = io.BytesIO(plaintext_archive)
    with tarfile.open(fileobj=tar_buffer, mode="r:gz") as tar:
        # Ensure safe extraction (prevent path traversal)
        def is_within_directory(directory: Path, target: Path) -> bool:
            try:
                directory.resolve().relative_to(target.resolve())
                return True
            except ValueError:
                return False

        for member in tar.getmembers():
            member_path = base_dir / member.name
            if not is_within_directory(member_path, base_dir):
                raise RuntimeError(f"Attempted Path Traversal in archive: {member.name}")

        # Python 3.12+ supports filter='data'
        if hasattr(tarfile, "data_filter"):
            tar.extractall(path=base_dir, filter="data")
        else:
            tar.extractall(path=base_dir)

    if progress_callback:
        progress_callback("שחזור הפרופיל למחשב הושלם בהצלחה!")


def wipe_profile_from_host(
    profile_id: str = "Default",
    user_data_dir: Optional[Path] = None,
    wipe_all: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None
) -> None:
    """
    Deletes the profile and/or Chrome User Data from the host computer
    to leave no traces on a public/shared computer.
    """
    base_dir = user_data_dir or get_chrome_user_data_dir()

    if not base_dir.exists():
        if progress_callback:
            progress_callback("לא נמצאו נתוני כרום למחיקה.")
        return

    if wipe_all:
        if progress_callback:
            progress_callback("מוחק את כל נתוני כרום מהמחשב...")
        shutil.rmtree(base_dir, ignore_errors=True)
    else:
        profile_path = base_dir / profile_id
        if profile_path.exists():
            if progress_callback:
                progress_callback(f"מוחק את נתוני הפרופיל {profile_id} מהמחשב...")
            shutil.rmtree(profile_path, ignore_errors=True)
        # Also remove Local State if no other profiles exist
        other_profiles = list_available_profiles(base_dir)
        if not other_profiles:
            local_state = base_dir / "Local State"
            if local_state.exists():
                local_state.unlink(missing_ok=True)

    if progress_callback:
        progress_callback("הניקוי מהמחשב הסתיים בהצלחה!")
