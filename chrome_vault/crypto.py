import os
import hashlib
import hmac

MAGIC_HEADER = b"CPV3"  # Chrome Profile Vault v3 (High-Speed C-Accelerated Standard Library)
SALT_SIZE = 16
NONCE_SIZE = 16
PBKDF2_ITERATIONS = 50_000

class CryptoError(Exception):
    """Raised when encryption or decryption fails (e.g. wrong password or corrupted data)."""
    pass

def _derive_keys(password: str, salt: bytes) -> tuple[bytes, bytes]:
    """
    Derives 64 bytes using PBKDF2-HMAC-SHA256 from standard library:
    - First 32 bytes: EncKey (for SHAKE-256 stream cipher keystream)
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

def _fast_keystream_xor(data: bytes, enc_key: bytes, nonce: bytes) -> bytes:
    """
    High-speed C-accelerated stream cipher using SHA-3 SHAKE256 and native 64-bit int XOR.
    Runs at hundreds of megabytes per second with zero external DLLs.
    """
    data_len = len(data)
    if data_len == 0:
        return b""

    # Native C-optimized SHAKE256 keystream generation
    shake = hashlib.shake_256(enc_key + nonce)
    keystream = shake.digest(data_len)

    # Fast XOR via native integer arithmetic
    xored_int = int.from_bytes(data, "little") ^ int.from_bytes(keystream, "little")
    return xored_int.to_bytes(data_len, "little")

def encrypt_data(plaintext: bytes, password: str) -> bytes:
    """
    Encrypts plaintext bytes at native C speeds without requiring any external DLLs.
    Format:
    MAGIC_HEADER (4B) + salt (16B) + nonce (16B) + ciphertext + HMAC-SHA256 Tag (32B)
    """
    if not password:
        raise CryptoError("קוד הגישה אינו יכול להיות ריק.")

    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    enc_key, auth_key = _derive_keys(password, salt)

    ciphertext = _fast_keystream_xor(plaintext, enc_key, nonce)

    # Compute HMAC-SHA256 tag over header + salt + nonce + ciphertext (Encrypt-then-MAC)
    h = hmac.new(auth_key, MAGIC_HEADER + salt + nonce + ciphertext, hashlib.sha256)
    tag = h.digest()

    return MAGIC_HEADER + salt + nonce + ciphertext + tag

def decrypt_data(encrypted_data: bytes, password: str) -> bytes:
    """
    Decrypts bytes, verifies authentication tag, and returns plaintext in seconds.
    Raises CryptoError if passcode is wrong or data is tampered.
    """
    min_len = len(MAGIC_HEADER) + SALT_SIZE + NONCE_SIZE + 32  # 32 is tag size
    if len(encrypted_data) < min_len:
        raise CryptoError("קובץ הכספת פגום או קצר מדי (Corrupted vault file)")

    header = encrypted_data[:len(MAGIC_HEADER)]
    if header != MAGIC_HEADER:
        raise CryptoError("פורמט קובץ כספת לא תקין או שנוצר בגרסה ישנה.")

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

    # Fast decrypt ciphertext
    plaintext = _fast_keystream_xor(ciphertext, enc_key, nonce)
    return plaintext
