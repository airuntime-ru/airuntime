import re

MAX_USER_MESSAGE_CHARS = 12_000
INJECTION_PATTERNS = (
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"disregard\s+(the\s+)?system\s+prompt",
    r"reveal\s+(the\s+)?(system|hidden)\s+prompt",
    r"print\s+(all\s+)?secrets",
)


def sanitize_user_message(content: str) -> str:
    trimmed = content.strip()
    if not trimmed:
        raise ValueError("Message cannot be empty")
    if len(trimmed) > MAX_USER_MESSAGE_CHARS:
        raise ValueError(f"Message exceeds {MAX_USER_MESSAGE_CHARS} characters")
    lowered = trimmed.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            raise ValueError("Message contains disallowed instruction patterns")
    return trimmed


def redact_secrets(text: str) -> str:
    return re.sub(
        r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        text,
    )
