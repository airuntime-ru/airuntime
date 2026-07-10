import base64
import hashlib
import re

from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models.project import Project
from src.db.models.secret import Secret

from cryptography.fernet import Fernet


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


TELEGRAM_BOT_TOKEN_KEY = "TELEGRAM_BOT_TOKEN"

# Keyword-based matching (not just alias sets) so loosely/differently named keys - including
# Cyrillic ones like "токен" or "мой бот токен" - still resolve to the canonical env var name
# an agent-generated bot actually reads (os.environ["TELEGRAM_BOT_TOKEN"]).
_TELEGRAM_MARKERS = ("telegram", "телеграм", "tg")
_TOKEN_MARKERS = ("token", "токен", "ключ", "key")
_BOT_MARKERS = ("bot", "бот")


def normalize_secret_key(value: str, *, project_type: str | None = None) -> str:
    raw = value.strip()
    lowered = raw.lower()
    has_telegram = any(marker in lowered for marker in _TELEGRAM_MARKERS)
    has_token = any(marker in lowered for marker in _TOKEN_MARKERS)
    has_bot = any(marker in lowered for marker in _BOT_MARKERS)
    looks_like_telegram_token = has_telegram and has_token
    looks_like_bot_token = has_bot and has_token
    # A bare "token"/"токен"/"ключ" only means the Telegram token when the project itself is a
    # Telegram bot (otherwise it's ambiguous - e.g. a website's payment provider key).
    bare_token = lowered in {"token", "токен", "ключ", "key"}
    if looks_like_telegram_token or looks_like_bot_token or (bare_token and project_type == "telegram_bot"):
        return TELEGRAM_BOT_TOKEN_KEY
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", raw.upper()).strip("_")
    return normalized or "SECRET"


def looks_like_telegram_token(value: str) -> bool:
    return bool(re.fullmatch(r"\d{6,}:[A-Za-z0-9_-]{20,}", value.strip()))


def ensure_secret_placeholder(
    db: Session, project: Project, key: str, reason: str = ""
) -> tuple[Secret, bool]:
    """Create an empty (value-less) secret slot if one doesn't already exist for this key.

    Returns (secret, created). Never overwrites an existing value or an existing reason with
    an empty one - safe to call repeatedly (e.g. once per agent turn).
    """
    normalized_key = normalize_secret_key(key, project_type=project.type)
    existing = (
        db.query(Secret)
        .filter(Secret.project_id == project.id, Secret.key == normalized_key)
        .first()
    )
    if existing:
        if reason and not existing.reason:
            existing.reason = reason
            db.add(existing)
            db.commit()
        return existing, False
    secret = Secret(project_id=project.id, key=normalized_key, reason=reason or None)
    db.add(secret)
    db.commit()
    db.refresh(secret)
    return secret, True
