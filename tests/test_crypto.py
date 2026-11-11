import pytest
from chrome_vault.crypto import encrypt_data, decrypt_data, CryptoError

def test_encryption_decryption_success():
    secret = b"My Chrome sensitive cookie data and session tokens"
    passcode = "Secret123!"

    encrypted = encrypt_data(secret, passcode)
    assert encrypted != secret
    assert len(encrypted) > len(secret)
    assert encrypted.startswith(b"CPV2")

    decrypted = decrypt_data(encrypted, passcode)
    assert decrypted == secret

def test_decryption_wrong_passcode():
    secret = b"Test secret"
    encrypted = encrypt_data(secret, "correct_passcode")

    with pytest.raises(CryptoError, match="קוד גישה שגוי"):
        decrypt_data(encrypted, "wrong_passcode")

def test_decryption_corrupted_data():
    with pytest.raises(CryptoError):
        decrypt_data(b"too_short", "any_passcode")

    secret = b"Test secret"
    encrypted = bytearray(encrypt_data(secret, "password"))
    # Corrupt last byte
    encrypted[-1] ^= 0xFF
    with pytest.raises(CryptoError):
        decrypt_data(bytes(encrypted), "password")
