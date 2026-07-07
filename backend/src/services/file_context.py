import json
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.chat_file import ChatFile
from src.services.storage import storage_service

TEXTUAL_PREFIXES = ("text/",)
TEXTUAL_TYPES = {
    "application/json",
    "application/javascript",
    "application/xml",
    "application/x-yaml",
}


def _is_textual(content_type: str, filename: str) -> bool:
    if content_type.startswith(TEXTUAL_PREFIXES):
        return True
    if content_type in TEXTUAL_TYPES:
        return True
    return filename.lower().endswith(
        (
            ".md",
            ".markdown",
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".json",
            ".yaml",
            ".yml",
            ".csv",
            ".txt",
            ".html",
            ".css",
            ".xml",
        )
    )


def attach_files_to_message(
    db: Session, *, message_id: UUID, attachment_ids: list[UUID]
) -> list[ChatFile]:
    if not attachment_ids:
        return []
    rows = db.query(ChatFile).filter(ChatFile.id.in_(attachment_ids)).all()
    if len(rows) != len(attachment_ids):
        raise ValueError("One or more attachments were not found")
    for row in rows:
        if row.message_id is not None:
            raise ValueError("Attachment already linked to a message")
        row.message_id = message_id
    db.commit()
    return rows


def build_attachment_context(db: Session, attachment_ids: list[UUID], *, max_chars: int) -> str:
    if not attachment_ids:
        return ""
    rows = (
        db.query(ChatFile)
        .filter(ChatFile.id.in_(attachment_ids))
        .order_by(ChatFile.created_at.asc())
        .all()
    )
    if not rows:
        return ""

    parts: list[str] = []
    remaining = max_chars
    for row in rows:
        header = f"Attachment: {row.original_filename} ({row.content_type}, {row.size_bytes} bytes)"
        if _is_textual(row.content_type, row.original_filename):
            preview = storage_service.read_text_preview(
                row.object_key, max_chars=min(remaining, 8000)
            )
            if preview:
                block = f"{header}\n```\n{preview}\n```"
            else:
                block = f"{header}\n[binary or unreadable text content omitted]"
        else:
            block = f"{header}\n[non-text attachment omitted from model context]"
        parts.append(block)
        remaining -= len(block)
        if remaining <= 0:
            break
    return "\n\n".join(parts)


def serialize_message_metadata(attachment_ids: list[UUID]) -> str:
    return json.dumps({"attachment_ids": [str(item) for item in attachment_ids]})
