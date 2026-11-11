import os
import pytest
from pathlib import Path
from chrome_vault.manager import (
    export_profile_to_vault,
    restore_profile_from_vault,
    wipe_profile_from_host,
    list_available_profiles,
)
from chrome_vault.crypto import CryptoError

@pytest.fixture
def fake_chrome_dir(tmp_path):
    chrome_dir = tmp_path / "chrome_user_data"
    chrome_dir.mkdir(parents=True)

    # Create Local State
    local_state = chrome_dir / "Local State"
    local_state.write_text('{"os_crypt": {"encrypted_key": "dummy_key"}}', encoding="utf-8")

    # Create Default profile
    default_dir = chrome_dir / "Default"
    default_dir.mkdir()
    (default_dir / "Preferences").write_text('{"account_info": "logged_in"}', encoding="utf-8")
    (default_dir / "Cookies").write_bytes(b"dummy cookies db")
    (default_dir / "History").write_bytes(b"dummy history db")

    # Create a cache dir that should be ignored
    cache_dir = default_dir / "Cache"
    cache_dir.mkdir()
    (cache_dir / "cache_data.bin").write_bytes(b"some temp cache")

    # Create Profile 1
    prof1_dir = chrome_dir / "Profile 1"
    prof1_dir.mkdir()
    (prof1_dir / "Preferences").write_text('{"account": "profile_1"}', encoding="utf-8")

    return chrome_dir

def test_list_available_profiles(fake_chrome_dir):
    profiles = list_available_profiles(fake_chrome_dir)
    profile_ids = [p["id"] for p in profiles]
    assert "Default" in profile_ids
    assert "Profile 1" in profile_ids

def test_export_and_restore_cycle(fake_chrome_dir, tmp_path):
    vault_file = tmp_path / "test_app_folder" / "profile.vault"
    vault_file.parent.mkdir()
    password = "MyStrongPassword456!"

    # 1. Export profile to vault
    exported_path = export_profile_to_vault(
        password=password,
        vault_path=vault_file,
        profile_id="Default",
        user_data_dir=fake_chrome_dir,
    )
    assert exported_path.exists()
    assert exported_path.stat().st_size > 0

    # 2. Simulate restoring on a new machine / empty chrome dir
    restore_chrome_dir = tmp_path / "restored_chrome_user_data"
    restore_chrome_dir.mkdir()

    restore_profile_from_vault(
        password=password,
        vault_path=vault_file,
        user_data_dir=restore_chrome_dir,
    )

    # Verify restored files
    assert (restore_chrome_dir / "Local State").exists()
    assert (restore_chrome_dir / "Local State").read_text(encoding="utf-8") == '{"os_crypt": {"encrypted_key": "dummy_key"}}'
    assert (restore_chrome_dir / "Default" / "Preferences").exists()
    assert (restore_chrome_dir / "Default" / "Cookies").read_bytes() == b"dummy cookies db"

    # Verify cache was filtered out
    assert not (restore_chrome_dir / "Default" / "Cache").exists()

def test_restore_wrong_password(fake_chrome_dir, tmp_path):
    vault_file = tmp_path / "profile.vault"
    password = "CorrectPassword"

    export_profile_to_vault(
        password=password,
        vault_path=vault_file,
        profile_id="Default",
        user_data_dir=fake_chrome_dir,
    )

    restore_chrome_dir = tmp_path / "new_chrome"
    restore_chrome_dir.mkdir()

    with pytest.raises(CryptoError):
        restore_profile_from_vault(
            password="WrongPassword",
            vault_path=vault_file,
            user_data_dir=restore_chrome_dir,
        )

def test_wipe_profile_from_host(fake_chrome_dir):
    assert (fake_chrome_dir / "Default").exists()
    assert (fake_chrome_dir / "Profile 1").exists()

    # Wipe only Default profile
    wipe_profile_from_host(
        profile_id="Default",
        user_data_dir=fake_chrome_dir,
        wipe_all=False,
    )

    assert not (fake_chrome_dir / "Default").exists()
    # Profile 1 should still be there
    assert (fake_chrome_dir / "Profile 1").exists()

    # Wipe Profile 1
    wipe_profile_from_host(
        profile_id="Profile 1",
        user_data_dir=fake_chrome_dir,
        wipe_all=False,
    )
    assert not (fake_chrome_dir / "Profile 1").exists()
    # Local State should now be cleaned up too
    assert not (fake_chrome_dir / "Local State").exists()

def test_wipe_all(fake_chrome_dir):
    assert fake_chrome_dir.exists()
    wipe_profile_from_host(
        user_data_dir=fake_chrome_dir,
        wipe_all=True,
    )
    assert not fake_chrome_dir.exists()
