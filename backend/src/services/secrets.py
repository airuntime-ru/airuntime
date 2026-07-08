import base64
import hashlib

from cryptography.fernet import Fernet

from src.core.config import settings


def _get_fernet() -> Fernet:
    if settings.app_encryption_key:
        key_bytes = settings.app_encryption_key.encode("utf-8")
        try:
            return Fernet(key_bytes)
        except ValueError:
            # Keep existing deployments working even when APP_ENCRYPTION_KEY
            # was provided in a non-Fernet format.
            derived = hashlib.sha256(key_bytes).digest()
            fallback_key = base64.urlsafe_b64encode(derived)
            return Fernet(fallback_key)
    derived = hashlib.sha256(settings.jwt_secret_key.encode("utf-8")).digest()
    fallback_key = base64.urlsafe_b64encode(derived)
    return Fernet(fallback_key)


def encrypt_secret(raw: str) -> str:
    token = _get_fernet().encrypt(raw.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(encrypted: str) -> str:
    raw = _get_fernet().decrypt(encrypted.encode("utf-8"))
    return raw.decode("utf-8")
