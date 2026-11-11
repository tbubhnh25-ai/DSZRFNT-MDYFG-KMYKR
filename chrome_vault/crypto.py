import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# Constants
SALT_SIZE = 16
NONCE_SIZE = 12
PBKDF2_ITERATIONS = 300_000
MAGIC_HEADER = b"CPV1"  # Chrome Profile Vault v1

class CryptoError(Exception):
    """Raised when encryption or decryption fails (e.g. wrong password)."""
    pass

def derive_key(password: str, salt: bytes) -> bytes:
    """Derives a 256-bit AES key from password and salt using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))

def encrypt_data(plaintext: bytes, password: str) -> bytes:
    """
    Encrypts bytes using AES-256-GCM.
    Returns: MAGIC_HEADER + salt (16B) + nonce (12B) + ciphertext_with_tag
    """
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=MAGIC_HEADER)
    return MAGIC_HEADER + salt + nonce + ciphertext

def decrypt_data(encrypted_data: bytes, password: str) -> bytes:
    """
    Decrypts bytes using AES-256-GCM.
    Verifies magic header, derives key, and authenticates ciphertext.
    """
    if len(encrypted_data) < len(MAGIC_HEADER) + SALT_SIZE + NONCE_SIZE + 16:
        raise CryptoError("קובץ הכספת פגום או קצר מדי (Corrupted vault file)")

    header = encrypted_data[:len(MAGIC_HEADER)]
    if header != MAGIC_HEADER:
        raise CryptoError("פורמט קובץ כספת לא תקין (Invalid vault file format)")

    offset = len(MAGIC_HEADER)
    salt = encrypted_data[offset:offset + SALT_SIZE]
    offset += SALT_SIZE
    nonce = encrypted_data[offset:offset + NONCE_SIZE]
    offset += NONCE_SIZE
    ciphertext = encrypted_data[offset:]

    key = derive_key(password, salt)
    aesgcm = AESGCM(key)

    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=MAGIC_HEADER)
        return plaintext
    except Exception as e:
        raise CryptoError("קוד גישה שגוי או שהקובץ פגום (Incorrect passcode or data corrupted)") from e
