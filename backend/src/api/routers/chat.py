import json
import re
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user
from src.api.dto.chat import (
    ChatCreateResponse,
    MessageCreateRequest,
    MessageResponse,
    StreamRequest,
)
from src.api.mappers.chat_files import chat_file_to_response
from src.core.config import settings
from src.db.models.chat import Chat
from src.db.models.chat_file import ChatFile
from src.db.models.message import Message
from src.db.models.project import Project
from src.db.models.user import User
from src.db.session import get_db
from src.services.agentic_artifacts import generate_project_artifact_agentic
from src.services.artifacts import ArtifactError, _telegram_token
from src.services.conversation import ConversationService
from src.services.deployments import create_deployment_for_project
from src.services.file_context import (
    attach_files_to_message,
    build_attachment_context,
    serialize_message_metadata,
)
from src.services.project_git import ProjectGitError, commit_snapshot
from src.services.project_intent import update_project_type_from_prompt
from src.services.project_runtime import RunningProjectLimitError
from src.services.project_subdomain import (
    assert_subdomain_available,
    normalize_deploy_subdomain,
    planned_public_url,
)
from src.services.prompt_guard import sanitize_user_message

router = APIRouter(prefix="/projects/{project_id}/chats", tags=["chat"])


class _StopDeployment(RuntimeError):
    pass


def _authorize_chat(
    db: Session, project_id: UUID, chat_id: UUID, current_user: User
) -> tuple[Project, Chat]:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    chat = db.get(Chat, chat_id)
    if not chat or chat.project_id != project_id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return project, chat


def _validate_attachments(
    db: Session,
    *,
    project_id: UUID,
    chat_id: UUID,
    user_id: UUID,
    attachment_ids: list[UUID],
    allow_linked: bool = False,
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
    if not allow_linked and any(row.message_id is not None for row in rows):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment already linked"
        )


def _compose_model_message(*, content: str, attachment_ids: list[UUID], db: Session) -> str:
    attachment_context = build_attachment_context(db, attachment_ids, max_chars=40_000)
    parts: list[str] = [
        (
            "Ты AIRuntime planner. Отвечай по-русски кратко и профессионально. "
            "Не выдавай большие блоки кода в чате: код будет создан отдельным агентом. "
            "Если задача недостаточно ясная, задай 2-4 уточняющих вопроса. "
            "Если информации достаточно, сначала коротко опиши план разработки."
        )
    ]
    if content.strip():
        parts.append(content.strip())
    if attachment_context:
        parts.append(attachment_context)
    return "\n\n".join(parts) if parts else "Review the attached project files."


def _needs_clarification(project: Project, content: str, attachment_ids: list[UUID]) -> bool:
    if attachment_ids:
        return False
    text = content.strip().lower()
    if not text:
        return True
    vague_phrases = (
        "сделай сайт",
        "сделай лендинг",
        "самый крутой",
        "крутой лендинг",
        "напиши бота",
        "сделай бота",
    )
    has_context = any(
        marker in text
        for marker in (
            "для ",
            "чтобы ",
            "котор",
            "клиент",
            "продаж",
            "заяв",
            "бренд",
            "стиль",
            "целевая",
        )
    )
    if len(text) < 26:
        return True
    return any(phrase in text for phrase in vague_phrases) and not has_context and not project.description


def _clarifying_questions(project: Project, content: str) -> str:
    if project.type == "telegram_bot":
        token_help_url = f"{settings.resolved_frontend_url}/help/telegram-token"
        return (
            "Перед разработкой бота нужно уточнить пару вещей:\n\n"
            "1. Где бот должен брать данные и что отвечать по умолчанию?\n"
            "2. Нужны ли команды вроде /start, /help, заявка, меню или сценарии?\n"
            "3. Добавьте секрет TELEGRAM_BOT_TOKEN в настройках проекта, чтобы я смог запустить бота.\n\n"
            "Как получить токен: откройте @BotFather в Telegram, выполните /newbot и скопируйте выданный token. "
            f"Инструкция: {token_help_url}\n\n"
            "После этого я соберу файлы, проверю Docker-сборку и запущу polling."
        )
    return (
        "Перед разработкой стоит уточнить основу проекта:\n\n"
        "1. Для кого этот продукт и какое действие пользователь должен совершить?\n"
        "2. Какие 3-5 блоков или функций точно нужны?\n"
        "3. Какой стиль ближе: минимальный, премиальный, playful, SaaS, editorial?\n"
        "4. Нужен ли конкретный поддомен или можно подобрать автоматически?\n\n"
        "Ответьте одним сообщением, и я соберу проект уже по нормальному плану."
    )


def _generated_files(path: Path, limit: int = 12) -> list[str]:
    files: list[str] = []
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(path).as_posix()
        if rel.startswith(".git/"):
            continue
        files.append(rel)
        if len(files) >= limit:
            break
    return files


def _extract_deploy_subdomain(text: str) -> str | None:
    """
    Extract requested deploy subdomain from user text.

    Supported patterns:
    - test.airuntime.ru
    - https://test.airuntime.ru
    - поддомен: test
    - subdomain = test
    """

    base_domain = settings.resolved_app_domain
    text_l = text.strip().lower()
    if not text_l:
        return None

    base_domain_escaped = re.escape(base_domain)
    for pattern in [
        rf"https?://([a-z0-9-]{{3,48}})\.{base_domain_escaped}",
        rf"\b([a-z0-9-]{{3,48}})\.{base_domain_escaped}\b",
        r"\bподдомен\s*[:=]?\s*([a-z0-9-]{3,48})\b",
        r"\bsubdomain\s*[:=]?\s*([a-z0-9-]{3,48})\b",
    ]:
        match = re.search(pattern, text_l, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _queue_deployment_or_notify_limit(db: Session, project: Project) -> str | None:
    try:
        create_deployment_for_project(db, project)
        return None
    except RunningProjectLimitError as exc:
        project.status = "ready"
        note = (
            f"{exc}\n"
            "Файлы проекта сохранены. Остановите один из запущенных проектов "
            "и запустите этот вручную на странице «Деплои»."
        )
        project.logs = f"{project.logs}\n{note}".strip() if project.logs else note
        db.add(project)
        return str(exc)


def _message_response(db: Session, message: Message) -> MessageResponse:
    files = db.query(ChatFile).filter(ChatFile.message_id == message.id).all()
    return MessageResponse(
        id=message.id,
        role=message.role,
        content_markdown=message.content_markdown,
        created_at=message.created_at,
        attachments=[chat_file_to_response(file) for file in files],
    )


def _sse_chunk(chunk: str) -> str:
    return f"data: {json.dumps({'chunk': chunk})}\n\n"


def _sse_status(phase: str, label: str, state: str = "running") -> str:
    return f"data: {json.dumps({'status': {'phase': phase, 'label': label, 'state': state}})}\n\n"


@router.post("", response_model=ChatCreateResponse)
def create_chat(
    project_id: UUID,
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
    project_id: UUID,
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
    return (
        db.query(Chat).filter(Chat.project_id == project_id).order_by(Chat.created_at.desc()).all()
    )


@router.get("/{chat_id}/messages", response_model=list[MessageResponse])
def list_messages(
    project_id: UUID,
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
    project_id: UUID,
    chat_id: UUID,
    payload: MessageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    project, _chat = _authorize_chat(db, project_id, chat_id, current_user)
    _validate_attachments(
        db,
        project_id=project.id,
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
    display_content = content or "Shared attachments"
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
    project: Project,
    chat_id: UUID,
    current_user: User,
    user_message: str,
    attachment_ids: list[UUID],
) -> StreamingResponse:
    if current_user.credits_balance <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits"
        )

    content = user_message.strip()
    if content:
        try:
            content = sanitize_user_message(content)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if content and update_project_type_from_prompt(project, content):
        db.add(project)
        db.commit()
        db.refresh(project)

    if project.type == "website" and content:
        extracted_subdomain = _extract_deploy_subdomain(content)
        if extracted_subdomain:
            normalized = normalize_deploy_subdomain(extracted_subdomain)
            assert_subdomain_available(db, normalized, exclude_project_id=str(project.id))
            project.deploy_subdomain = normalized
            db.add(project)
            db.commit()
            db.refresh(project)

    model_message = _compose_model_message(content=content, attachment_ids=attachment_ids, db=db)
    try:
        safe_message = sanitize_user_message(model_message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    conversation = ConversationService()

    async def event_source():
        assistant_full = ""

        def append_visible(text: str) -> str:
            nonlocal assistant_full
            assistant_full += text
            return _sse_chunk(text)

        if _needs_clarification(project, content, attachment_ids):
            questions = _clarifying_questions(project, content)
            yield _sse_status("questions", "Жду ответы на уточняющие вопросы", "done")
            yield append_visible(questions)
            assistant_message = Message(
                chat_id=chat_id, role="assistant", content_markdown=assistant_full
            )
            db.add(assistant_message)
            usage_cost = max(100, len(safe_message) + len(assistant_full))
            current_user.credits_balance = max(0, current_user.credits_balance - usage_cost)
            db.add(current_user)
            db.commit()
            yield "data: [DONE]\n\n"
            return

        yield _sse_status("thinking", "AIRuntime осмысляет задачу")
        if attachment_ids:
            yield _sse_status(
                "context",
                f"Читаю вложения и готовлю контекст: {len(attachment_ids)} файл(ов)",
            )
        async for chunk in conversation.stream_reply(
            chat_id=str(chat_id), user_message=safe_message
        ):
            yield append_visible(chunk)
        try:
            yield _sse_status("plan", "Проектирую структуру и модули")
            yield _sse_status("artifact", "Генерирую файлы проекта")
            yield append_visible("\n\nСоздаю файлы проекта и проверяю структуру...")
            artifact_path = await generate_project_artifact_agentic(db, project, safe_message)
            for rel_path in _generated_files(artifact_path):
                yield _sse_status("module", f"Модуль готов: {rel_path}")
            git_commit_hash: str | None = None
            try:
                yield _sse_status("version", "Сохраняю версию проекта")
                git_commit_hash = commit_snapshot(
                    artifact_path,
                    message=f"{project.name}: {safe_message}",
                )
            except ProjectGitError as git_exc:
                # Git errors shouldn't break the build/deploy pipeline.
                project.logs = f"Generated artifact: {artifact_path}\nGit error: {git_exc}"

            project.status = "ready"
            if git_commit_hash:
                project.logs = (
                    f"Generated artifact: {artifact_path}\nGit commit: {git_commit_hash}"
                )
            elif not project.logs:
                project.logs = f"Generated artifact: {artifact_path}"
            db.add(project)
            if project.type == "website" and settings.auto_deploy_websites:
                yield _sse_status("deploy", "Ставлю сайт в очередь запуска")
                planned_url = planned_public_url(project)
                limit_message = _queue_deployment_or_notify_limit(db, project)
                if limit_message:
                    yield _sse_status("limit", limit_message, "error")
                    yield append_visible(f"\n\n{limit_message}")
                elif planned_url:
                    yield append_visible(
                        f"\n\nСайт собран и поставлен в очередь на запуск. URL: {planned_url}"
                    )
                else:
                    yield append_visible(
                        "\n\nСайт собран и поставлен в очередь на запуск."
                    )
            elif project.type == "telegram_bot":
                if not _telegram_token(db, project):
                    token_help_url = f"{settings.resolved_frontend_url}/help/telegram-token"
                    project.status = "needs_configuration"
                    token_note = (
                        "Файлы бота созданы, но запуск остановлен: добавьте секрет "
                        "TELEGRAM_BOT_TOKEN в настройках проекта и повторите запуск.\n\n"
                        "Как получить токен: откройте @BotFather в Telegram, выполните /newbot "
                        f"и скопируйте выданный token. Инструкция: {token_help_url}"
                    )
                    project.logs = f"{project.logs}\n{token_note}".strip()
                    db.add(project)
                    yield _sse_status("needs_configuration", "Нужен TELEGRAM_BOT_TOKEN", "error")
                    yield append_visible(f"\n\n{token_note}")
                    raise _StopDeployment
                yield _sse_status("deploy", "Ставлю бота в очередь запуска")
                limit_message = _queue_deployment_or_notify_limit(db, project)
                if limit_message:
                    yield _sse_status("limit", limit_message, "error")
                    yield append_visible(f"\n\n{limit_message}")
                else:
                    yield append_visible("\n\nБот собран и поставлен в очередь на запуск.")
            yield _sse_status("done", "Готово: проект передан на запуск", "done")
        except _StopDeployment:
            pass
        except RunningProjectLimitError as exc:
            project.status = "ready"
            project.logs = f"{project.logs}\n{exc}".strip() if project.logs else str(exc)
            db.add(project)
            yield _sse_status("limit", "Достигнут лимит запущенных проектов", "error")
            yield append_visible(f"\n\n{exc}")
        except ArtifactError as exc:
            project.status = "needs_configuration"
            project.logs = str(exc)
            db.add(project)
            yield _sse_status("error", f"Нужно действие: {exc}", "error")
            yield append_visible(f"\n\nНужно действие: {exc}")

        assistant_message = Message(
            chat_id=chat_id, role="assistant", content_markdown=assistant_full
        )
        db.add(assistant_message)
        usage_cost = max(100, len(safe_message) + len(assistant_full))
        current_user.credits_balance = max(0, current_user.credits_balance - usage_cost)
        db.add(current_user)
        db.commit()
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.post("/{chat_id}/stream")
async def stream_reply_post(
    project_id: UUID,
    chat_id: UUID,
    payload: StreamRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    project, _chat = _authorize_chat(db, project_id, chat_id, current_user)
    _validate_attachments(
        db,
        project_id=project.id,
        chat_id=chat_id,
        user_id=current_user.id,
        attachment_ids=payload.attachment_ids,
        allow_linked=True,
    )
    return await _stream_events(
        db=db,
        project=project,
        chat_id=chat_id,
        current_user=current_user,
        user_message=payload.content,
        attachment_ids=payload.attachment_ids,
    )


@router.get("/{chat_id}/stream")
async def stream_reply_get(
    project_id: UUID,
    chat_id: UUID,
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    project, _chat = _authorize_chat(db, project_id, chat_id, current_user)
    return await _stream_events(
        db=db,
        project=project,
        chat_id=chat_id,
        current_user=current_user,
        user_message=q,
        attachment_ids=[],
    )
