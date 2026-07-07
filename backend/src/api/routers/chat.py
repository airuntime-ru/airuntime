import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user
from src.api.mappers.chat_files import chat_file_to_response
from src.api.dto.chat import ChatCreateResponse, MessageCreateRequest, MessageResponse, StreamRequest
from src.db.models.chat import Chat
from src.db.models.chat_file import ChatFile
from src.db.models.message import Message
from src.db.models.project import Project
from src.db.models.user import User
from src.db.session import get_db
from src.services.conversation import ConversationService
from src.services.file_context import (
    attach_files_to_message,
    build_attachment_context,
    serialize_message_metadata,
)
from src.services.prompt_guard import sanitize_user_message

router = APIRouter(prefix="/projects/{project_id}/chats", tags=["chat"])


def _authorize_chat(
    db: Session, project_id: str, chat_id: UUID, current_user: User
) -> tuple[Project, Chat]:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    chat = db.get(Chat, chat_id)
    if not chat or str(chat.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return project, chat


def _validate_attachments(
    db: Session,
    *,
    project_id: str,
    chat_id: UUID,
    user_id: UUID,
    attachment_ids: list[UUID],
) -> None:
    if not attachment_ids:
        return
    rows = (
        db.query(ChatFile)
        .filter(
            ChatFile.id.in_(attachment_ids),
            ChatFile.project_id == project_id,
            ChatFile.chat_id == chat_id,
            ChatFile.user_id == user_id,
        )
        .all()
    )
    if len(rows) != len(attachment_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid attachments")
    if any(row.message_id is not None for row in rows):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment already linked")


def _compose_model_message(*, content: str, attachment_ids: list[UUID], db: Session) -> str:
    attachment_context = build_attachment_context(db, attachment_ids, max_chars=40_000)
    parts: list[str] = []
    if content.strip():
        parts.append(content.strip())
    if attachment_context:
        parts.append(attachment_context)
    return "\n\n".join(parts) if parts else "Review the attached project files."


def _message_response(db: Session, message: Message) -> MessageResponse:
    files = db.query(ChatFile).filter(ChatFile.message_id == message.id).all()
    return MessageResponse(
        id=message.id,
        role=message.role,
        content_markdown=message.content_markdown,
        created_at=message.created_at,
        attachments=[chat_file_to_response(file) for file in files],
    )


@router.post("", response_model=ChatCreateResponse)
def create_chat(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Chat:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    chat = Chat(project_id=project.id, title=f"{project.name} chat")
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@router.get("", response_model=list[ChatCreateResponse])
def list_chats(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Chat]:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(Chat).filter(Chat.project_id == project_id).order_by(Chat.created_at.desc()).all()


@router.get("/{chat_id}/messages", response_model=list[MessageResponse])
def list_messages(
    project_id: str,
    chat_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageResponse]:
    _authorize_chat(db, project_id, chat_id, current_user)
    messages = (
        db.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return [_message_response(db, message) for message in messages]


@router.post("/{chat_id}/messages", response_model=MessageResponse)
def create_message(
    project_id: str,
    chat_id: UUID,
    payload: MessageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    project, _chat = _authorize_chat(db, project_id, chat_id, current_user)
    _validate_attachments(
        db,
        project_id=str(project.id),
        chat_id=chat_id,
        user_id=current_user.id,
        attachment_ids=payload.attachment_ids,
    )
    content = payload.content.strip()
    if content:
        try:
            content = sanitize_user_message(content)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    display_content = content or "📎 Shared attachments"
    message = Message(
        chat_id=chat_id,
        role="user",
        content_markdown=display_content,
        metadata_json=serialize_message_metadata(payload.attachment_ids),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    try:
        attach_files_to_message(db, message_id=message.id, attachment_ids=payload.attachment_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _message_response(db, message)


async def _stream_events(
    *,
    db: Session,
    chat_id: UUID,
    current_user: User,
    user_message: str,
    attachment_ids: list[UUID],
) -> StreamingResponse:
    if current_user.credits_balance <= 0:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits")

    content = user_message.strip()
    if content:
        try:
            content = sanitize_user_message(content)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    model_message = _compose_model_message(content=content, attachment_ids=attachment_ids, db=db)
    try:
        safe_message = sanitize_user_message(model_message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    conversation = ConversationService()

    async def event_source():
        assistant_full = ""
        async for chunk in conversation.stream_reply(chat_id=str(chat_id), user_message=safe_message):
            assistant_full += chunk
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        assistant_message = Message(chat_id=chat_id, role="assistant", content_markdown=assistant_full)
        db.add(assistant_message)
        usage_cost = max(100, len(safe_message) + len(assistant_full))
        current_user.credits_balance = max(0, current_user.credits_balance - usage_cost)
        db.add(current_user)
        db.commit()
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.post("/{chat_id}/stream")
async def stream_reply_post(
    project_id: str,
    chat_id: UUID,
    payload: StreamRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    project, _chat = _authorize_chat(db, project_id, chat_id, current_user)
    _validate_attachments(
        db,
        project_id=str(project.id),
        chat_id=chat_id,
        user_id=current_user.id,
        attachment_ids=payload.attachment_ids,
    )
    return await _stream_events(
        db=db,
        chat_id=chat_id,
        current_user=current_user,
        user_message=payload.content,
        attachment_ids=payload.attachment_ids,
    )


@router.get("/{chat_id}/stream")
async def stream_reply_get(
    project_id: str,
    chat_id: UUID,
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    _authorize_chat(db, project_id, chat_id, current_user)
    return await _stream_events(
        db=db,
        chat_id=chat_id,
        current_user=current_user,
        user_message=q,
        attachment_ids=[],
    )
