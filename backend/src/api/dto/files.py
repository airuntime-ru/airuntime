from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ChatFileResponse(BaseModel):
    id: UUID
    project_id: UUID
    chat_id: UUID
    message_id: UUID | None
    original_filename: str
    content_type: str
    size_bytes: int
    download_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreateRequest(BaseModel):
    content: str = Field(default="", max_length=12_000)
    attachment_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content_or_attachments(self) -> "MessageCreateRequest":
        if not self.content.strip() and not self.attachment_ids:
            raise ValueError("Message must include text or attachments")
        return self


class StreamRequest(BaseModel):
    content: str = Field(default="", max_length=12_000)
    attachment_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content_or_attachments(self) -> "StreamRequest":
        if not self.content.strip() and not self.attachment_ids:
            raise ValueError("Message must include text or attachments")
        return self
