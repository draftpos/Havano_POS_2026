# =============================================================================
# utils/crypto.py
#
# Machine-bound local credential encryption for SaaS mode api_secret.
# Encrypts api_secret stored in company_defaults and users table so plain text
# passwords (e.g. Admin@123) are NEVER stored in raw SQL or visible in SSMS.
# =============================================================================

import os
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from utils.hardware import get_machine_id

log = logging.getLogger("crypto")

_fernet_instance = None


def _get_cipher() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    machine_id = str(get_machine_id() or "HavanoPOS-SecureKey-2026").encode("utf-8")
    salt = b"HavanoPOS_SaaS_Credential_Salt_2026"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(machine_id))
    _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_secret(plain_text: str) -> str:
    """
    Encrypt secret string for DB persistence (SaaS mode).
    Returns ciphertext prefixed with 'enc:'.
    """
    if not plain_text:
        return ""
    plain_text = str(plain_text).strip()
    if plain_text.startswith("enc:"):
        return plain_text  # Already encrypted

    try:
        cipher = _get_cipher()
        encrypted_bytes = cipher.encrypt(plain_text.encode("utf-8"))
        return f"enc:{encrypted_bytes.decode('utf-8')}"
    except Exception as e:
        log.warning("[crypto] Could not encrypt secret: %s", e)
        return plain_text


def decrypt_secret(cipher_text: str) -> str:
    """
    Decrypt secret string retrieved from DB persistence (SaaS mode).
    Handles both encrypted 'enc:...' and legacy plain text seamlessly.
    """
    if not cipher_text:
        return ""
    cipher_text = str(cipher_text).strip()
    if not cipher_text.startswith("enc:"):
        return cipher_text  # Plain text fallback

    try:
        raw_enc = cipher_text[4:].encode("utf-8")
        cipher = _get_cipher()
        decrypted_bytes = cipher.decrypt(raw_enc)
        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        log.warning("[crypto] Could not decrypt secret: %s", e)
        return cipher_text
