import os
import hashlib
import hmac

MAGIC_HEADER = b"CPV2"  # Chrome Profile Vault v2 (Standard-library Zero-DLL engine)
SALT_SIZE = 16
NONCE_SIZE = 16
PBKDF2_ITERATIONS = 200_000

class CryptoError(Exception):
    """Raised when encryption or decryption fails (e.g. wrong password or corrupted data)."""
    pass

def _derive_keys(password: str, salt: bytes) -> tuple[bytes, bytes]:
    """
    Derives 64 bytes using PBKDF2-HMAC-SHA256 from standard library:
    - First 32 bytes: EncKey (for stream cipher / keystream)
    - Next 32 bytes: AuthKey (for HMAC-SHA256 authenticated encryption)
    """
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=64
    )
    return derived[:32], derived[32:]

def _keystream_xor(data: bytes, enc_key: bytes, nonce: bytes) -> bytes:
    """
    CTR-style keystream generator using SHA-256 blocks (standard library only).
    """
    out = bytearray(len(data))
    block_index = 0
    data_len = len(data)

    for offset in range(0, data_len, 32):
        counter = block_index.to_bytes(8, "big")
        keystream_block = hashlib.sha256(enc_key + nonce + counter).digest()
        chunk_len = min(32, data_len - offset)
        for i in range(chunk_len):
            out[offset + i] = data[offset + i] ^ keystream_block[i]
        block_index += 1

    return bytes(out)

def encrypt_data(plaintext: bytes, password: str) -> bytes:
    """
    Encrypts plaintext bytes with zero C-extension/DLL dependencies (100% pure Python standard library).
    Format:
    MAGIC_HEADER (4B) + salt (16B) + nonce (16B) + ciphertext + HMAC-SHA256 Tag (32B)
    """
    if not password:
        raise CryptoError("קוד הגישה אינו יכול להיות ריק.")

    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    enc_key, auth_key = _derive_keys(password, salt)

    ciphertext = _keystream_xor(plaintext, enc_key, nonce)

    # Compute HMAC tag over header + salt + nonce + ciphertext (Encrypt-then-MAC)
    h = hmac.new(auth_key, MAGIC_HEADER + salt + nonce + ciphertext, hashlib.sha256)
    tag = h.digest()

    return MAGIC_HEADER + salt + nonce + ciphertext + tag

def decrypt_data(encrypted_data: bytes, password: str) -> bytes:
    """
    Decrypts bytes, verifies authentication tag, and returns plaintext.
    Raises CryptoError if passcode is wrong or data is tampered.
    """
    min_len = len(MAGIC_HEADER) + SALT_SIZE + NONCE_SIZE + 32  # 32 is tag size
    if len(encrypted_data) < min_len:
        raise CryptoError("קובץ הכספת פגום או קצר מדי (Corrupted vault file)")

    header = encrypted_data[:len(MAGIC_HEADER)]
    if header != MAGIC_HEADER:
        raise CryptoError("פורמט קובץ כספת לא תקין או שנוצר בגרסה אחרת.")

    offset = len(MAGIC_HEADER)
    salt = encrypted_data[offset:offset + SALT_SIZE]
    offset += SALT_SIZE
    nonce = encrypted_data[offset:offset + NONCE_SIZE]
    offset += NONCE_SIZE

    tag = encrypted_data[-32:]
    ciphertext = encrypted_data[offset:-32]

    enc_key, auth_key = _derive_keys(password, salt)

    # Verify HMAC tag (constant time comparison)
    expected_mac = hmac.new(auth_key, MAGIC_HEADER + salt + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_mac):
        raise CryptoError("קוד גישה שגוי או שהקובץ פגום (Incorrect passcode or data corrupted)")

    # Decrypt ciphertext
    plaintext = _keystream_xor(ciphertext, enc_key, nonce)
    return plaintext
