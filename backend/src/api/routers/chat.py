import asyncio
import json
import re
import time
from datetime import UTC, datetime
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
from src.db.models.deployment import Deployment
from src.db.models.message import Message
from src.db.models.moderation_event import ModerationEvent
from src.db.models.project import Project
from src.db.models.project_service import ProjectService
from src.db.models.user import User
from src.db.session import get_db
from src.services.agent.events import AgentDone, TextDelta, ToolCallRequested, ToolCallResult
from src.services.agent.loop import CodingAgentSession
from src.services.agent.prompt import build_system_prompt
from src.services.agent.tools import WorkspaceTools
from src.services.agentic_artifacts import (
    ensure_dockerfile,
    ensure_required_files,
    thin_bot_architecture_warning,
    workspace_has_agent_code,
)
from src.services.artifacts import ArtifactError, _telegram_token
from src.services.billing import record_usage
from src.services.chat_context import build_llm_context
from src.services.deployments import create_deployment_for_project, store_deployment_error
from src.services.file_context import (
    attach_files_to_message,
    build_attachment_context,
    extract_image_attachments,
    serialize_message_metadata,
)
from src.services.moderation import (
    check_project_safety,
    is_token_related_block_reason,
)
from src.services.project_git import ProjectGitError, commit_snapshot
from src.services.project_intent import (
    can_update_project_type,
    reconcile_type_with_workspace,
    update_project_type_from_prompt,
)
from src.services.project_runtime import RunningProjectLimitError, block_project, unblock_project
from src.services.project_services import (
    ProjectServiceError,
    ensure_service_request,
    is_likely_service_credential_key,
)
from src.services.project_subdomain import (
    assert_subdomain_available,
    normalize_deploy_subdomain,
)
from src.services.prompt_guard import sanitize_user_message
from src.services.provider.factory import resolve_provider_and_model
from src.services.secrets import capture_telegram_tokens_from_text, ensure_secret_placeholder
from src.services.system_settings import resolve_api_key_for_provider
from src.services.workspace import project_dir

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


def _compose_user_message(*, content: str, attachment_ids: list[UUID], db: Session) -> str:
    """Builds the raw text handed to the coding agent as this turn's user message.

    Persona/behavior rules live in the system prompt (src/services/agent/prompt.py) now,
    not here - this only assembles what the user actually said plus attachment context.
    """

    attachment_context = build_attachment_context(db, attachment_ids, max_chars=40_000)
    parts: list[str] = []
    if content.strip():
        parts.append(content.strip())
    if attachment_context:
        parts.append(attachment_context)
    return (
        "\n\n".join(parts) if parts else "Пользователь прикрепил файлы без текста - изучи вложения."
    )


def _tool_status_label(name: str, arguments: dict) -> str:
    path = arguments.get("path", "") if isinstance(arguments, dict) else ""
    if name == "list_files":
        return "Изучаю структуру проекта" + (f": {path}" if path and path != "." else "")
    if name == "read_file":
        return f"Читаю {path}"
    if name == "write_file":
        return f"Пишу {path}"
    if name == "edit_file":
        return f"Правлю {path}"
    if name == "delete_file":
        return f"Удаляю {path}"
    if name == "request_secret":
        key = arguments.get("key", "") if isinstance(arguments, dict) else ""
        return f"Запрашиваю секрет {key}" if key else "Запрашиваю секрет"
    if name == "request_service":
        kind = arguments.get("kind", "") if isinstance(arguments, dict) else ""
        return f"Запрашиваю сервис {kind}" if kind else "Запрашиваю сервис"
    return f"Инструмент: {name}"


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
    - поддомен: test / домен: test
    - subdomain = test
    - Free-form Russian like "домен хочу test" or "пусть домен будет test" - falls back to
      the first Latin-alphabet token found shortly after the word "домен"/"поддомен".
    """

    base_domain = settings.resolved_app_domain
    text_l = text.strip().lower()
    if not text_l:
        return None

    base_domain_escaped = re.escape(base_domain)
    base_domain_labels = {label for label in base_domain.split(".") if label}
    for pattern in [
        rf"https?://([a-z0-9-]{{3,48}})\.{base_domain_escaped}",
        rf"\b([a-z0-9-]{{3,48}})\.{base_domain_escaped}\b",
        r"\bпод ?домен\w*\s*[:=]?\s*([a-z0-9-]{3,48})\b",
        r"\bдомен\w*\s*[:=]?\s*([a-z0-9-]{3,48})\b",
        r"\bsubdomain\s*[:=]?\s*([a-z0-9-]{3,48})\b",
    ]:
        match = re.search(pattern, text_l, flags=re.IGNORECASE)
        if match and match.group(1) not in base_domain_labels:
            return match.group(1)

    # Loose fallback: user mentioned "домен"/"поддомен" but phrased it as a sentence
    # ("домен хочу morning-coffee") rather than "домен: x" - grab the first Latin-script
    # token within a short window after the word, skipping the base domain's own labels.
    domain_word = re.search(r"под ?домен\w*|домен\w*|subdomain", text_l)
    if domain_word:
        window = text_l[domain_word.end() : domain_word.end() + 60]
        for candidate in re.finditer(r"\b([a-z][a-z0-9-]{2,47})\b", window):
            token = candidate.group(1)
            if token not in base_domain_labels and token not in {"the", "for", "and"}:
                return token
    return None


_DEPLOYMENT_TERMINAL = frozenset({"completed", "failed", "cancelled", "stopped"})
_DEPLOY_WAIT_SECONDS = 300
_DEPLOY_POLL_SECONDS = 2.0
# Post-deploy auto-check sleeps ~3s then may start a repair redeploy - wait past that
# before declaring success so chat doesn't claim "live" while the follow-up fails.
_DEPLOY_SETTLE_SECONDS = 6.0


def _queue_deployment_or_notify_limit(
    db: Session, project: Project
) -> tuple[Deployment | None, str | None]:
    try:
        deployment = create_deployment_for_project(db, project)
        return deployment, None
    except RunningProjectLimitError as exc:
        project.status = "ready"
        note = (
            f"{exc}\n"
            "Файлы проекта сохранены. Остановите один из запущенных проектов "
            "и запустите этот вручную на странице «Деплои»."
        )
        project.logs = f"{project.logs}\n{note}".strip() if project.logs else note
        db.add(project)
        return None, str(exc)


def _deploy_status_label(deployment_status: str) -> str:
    if deployment_status == "queued":
        return "В очереди на запуск"
    if deployment_status == "running":
        return "Собираю образ и запускаю контейнер"
    if deployment_status == "completed":
        return "Контейнер запущен"
    if deployment_status == "failed":
        return "Запуск не удался"
    return f"Статус деплоя: {deployment_status}"


def _launch_success_message(project: Project, *, has_website: bool, has_bot: bool) -> str:
    url = (project.deployment_url or "").strip()
    if has_website and has_bot:
        if url:
            return f"\n\nСайт и бот запущены и работают. Сайт: {url}"
        return "\n\nСайт и бот запущены и работают."
    if has_website:
        if url:
            return f"\n\nСайт запущен и доступен: {url}"
        return "\n\nСайт запущен и работает."
    if url:
        return f"\n\nБот запущен и работает: {url}"
    return "\n\nБот запущен и работает."


def _launch_failure_message(deployment: Deployment | None, project: Project) -> str:
    detail = ""
    if deployment and deployment.error_text:
        detail = deployment.error_text.strip()[-4000:]
    elif deployment and deployment.logs_ref and not deployment.logs_ref.startswith("docker://"):
        detail = deployment.logs_ref.strip()
    elif project.logs:
        # Prefer the last deployment-related note from project logs.
        for line in reversed(project.logs.strip().splitlines()):
            if "Deployment failed" in line or "failed" in line.lower():
                detail = line.strip()
                break
        if not detail:
            detail = project.logs.strip().splitlines()[-1][:500]
    if detail:
        return f"\n\nНе удалось запустить проект: {detail}"
    return (
        "\n\nНе удалось запустить проект. Подробности — во вкладках «Деплои» и «Логи»."
    )


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
        # Persist BotFather tokens into secrets and keep the raw value out of chat history.
        content = capture_telegram_tokens_from_text(db, project, content)
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
    provider_override: str | None = None,
    model_override: str | None = None,
) -> StreamingResponse:
    if current_user.credits_balance <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits"
        )
    if current_user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован администратором"
            + (f": {current_user.banned_reason}" if current_user.banned_reason else "."),
        )
    if project.status == "blocked":
        # Pasting a BotFather token used to be auto-flagged as scam - heal those blocks in place
        # so the user does not need an admin to continue.
        if is_token_related_block_reason(project.blocked_reason):
            unblock_project(db, project)
            db.add(
                ModerationEvent(
                    project_id=project.id,
                    project_name=project.name,
                    user_id=current_user.id,
                    action="unblocked",
                    category="",
                    reason="Авто: ложное срабатывание на токен Telegram-бота",
                )
            )
            db.commit()
            db.refresh(project)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Проект заблокирован модерацией"
                + (f": {project.blocked_reason}" if project.blocked_reason else "."),
            )

    content = user_message.strip()
    if content:
        try:
            content = sanitize_user_message(content)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        content = capture_telegram_tokens_from_text(db, project, content)

    # Only allowed to move away from the initial guess while nothing has been generated yet -
    # once a project has real files/a deploy, a later message mentioning an unrelated word
    # (e.g. any form of "работать") must not silently flip it to a different project type.
    if (
        content
        and can_update_project_type(project)
        and update_project_type_from_prompt(project, content)
    ):
        db.add(project)
        db.commit()
        db.refresh(project)

    # Not gated on project.type == "website": a domain mention is deliberate user intent that
    # must never be silently dropped, even if the project's current type classification (set
    # from an earlier message, or about to change) doesn't happen to be "website" right now.
    if content:
        extracted_subdomain = _extract_deploy_subdomain(content)
        if extracted_subdomain:
            normalized = normalize_deploy_subdomain(extracted_subdomain)
            assert_subdomain_available(db, normalized, exclude_project_id=str(project.id))
            project.deploy_subdomain = normalized
            db.add(project)
            db.commit()
            db.refresh(project)

    user_agent_message = _compose_user_message(
        content=content, attachment_ids=attachment_ids, db=db
    )
    try:
        safe_message = sanitize_user_message(user_agent_message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    image_attachments = extract_image_attachments(db, attachment_ids)

    provider_name, model = resolve_provider_and_model(
        provider_override=provider_override,
        model_override=model_override,
    )
    api_key = (
        resolve_api_key_for_provider(provider_name)
        or getattr(settings, f"{provider_name}_api_key", None)
        or ""
    )

    if content:
        verdict = await check_project_safety(
            text=content, provider_name=provider_name, model=model, api_key=api_key
        )
        if verdict.blocked:
            reason = f"{verdict.category}: {verdict.reason}" if verdict.reason else verdict.category
            block_project(db, project, reason=reason)
            db.add(
                ModerationEvent(
                    project_id=project.id,
                    project_name=project.name,
                    user_id=current_user.id,
                    action="flagged",
                    category=verdict.category,
                    reason=verdict.reason,
                )
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Проект заблокирован модерацией: {reason}",
            )

    async def event_source():
        assistant_full = ""

        def append_visible(text: str) -> str:
            nonlocal assistant_full
            assistant_full += text
            return _sse_chunk(text)

        yield _sse_status("thinking", "AIRuntime осмысляет задачу")
        if attachment_ids:
            yield _sse_status(
                "context",
                f"Читаю вложения и готовлю контекст: {len(attachment_ids)} файл(ов)",
            )

        artifact_path = project_dir(project.id)
        agent_error: str | None = None
        requested_secret_keys: set[str] = set()

        if not api_key:
            yield append_visible(
                "AI-провайдер не настроен (нет API ключа). Без агента проект не соберётся — "
                "шаблоны отключены. Настройте ключ провайдера и повторите запрос."
            )
            yield _sse_status("error", "Нет API-ключа провайдера", "error")
        else:
            history, summary = await build_llm_context(
                db, chat_id, provider_name=provider_name, model=model, api_key=api_key
            )
            system_prompt = build_system_prompt(project)
            if summary:
                system_prompt += f"\n\nКонтекст более раннего диалога в этом чате:\n{summary}"

            workspace = WorkspaceTools(artifact_path, project_id=str(project.id))
            session = CodingAgentSession(
                provider_name=provider_name,
                model=model,
                api_key=api_key,
                workspace=workspace,
                system_prompt=system_prompt,
            )

            async for event in session.run(
                history=history, user_message=safe_message, images=image_attachments
            ):
                if isinstance(event, TextDelta):
                    yield append_visible(event.text)
                elif isinstance(event, ToolCallRequested):
                    yield _sse_status("tool", _tool_status_label(event.name, event.arguments))
                elif isinstance(event, ToolCallResult):
                    icon = "✓" if event.ok else "⚠"
                    yield _sse_status(
                        "tool", f"{icon} {event.summary}", "done" if event.ok else "error"
                    )
                elif isinstance(event, AgentDone) and event.reason == "error":
                    agent_error = event.error

            existing_service_kinds = {
                row.kind
                for row in db.query(ProjectService)
                .filter(ProjectService.project_id == project.id)
                .all()
            }

            new_service_lines: list[str] = []
            for service_request in workspace.requested_services:
                try:
                    service_row, created = ensure_service_request(
                        db,
                        project,
                        service_request.kind,
                        service_request.reason,
                        image=service_request.image,
                        env=service_request.env,
                        data_path=service_request.data_path,
                    )
                except ProjectServiceError:
                    continue
                existing_service_kinds.add(service_row.kind)
                reason = service_request.reason
                if created:
                    label = f"**{service_row.kind}** ({service_row.image})"
                    new_service_lines.append(f"- {label} - {reason}" if reason else f"- {label}")

            new_secret_lines: list[str] = []
            for key, reason in workspace.requested_secrets:
                if is_likely_service_credential_key(key, existing_service_kinds):
                    # The agent asked for a piece of a service it already provisioned via
                    # request_service (e.g. POSTGRES_PASSWORD) - that's already generated and
                    # wired up automatically, so there's nothing for the user to fill in here.
                    continue
                secret_row, created = ensure_secret_placeholder(db, project, key, reason)
                requested_secret_keys.add(secret_row.key)
                if created:
                    label = f"**{secret_row.key}**"
                    new_secret_lines.append(f"- {label} - {reason}" if reason else f"- {label}")
            if new_secret_lines:
                yield append_visible(
                    "\n\nЧтобы проект заработал, заполните в настройках проекта "
                    "(вкладка «Настройки») эти значения:\n" + "\n".join(new_secret_lines)
                )
            if new_service_lines:
                yield append_visible(
                    "\n\nПодключаю для проекта:\n"
                    + "\n".join(new_service_lines)
                    + "\n\nСервис поднимется автоматически при следующем запуске проекта."
                )

            if agent_error:
                lowered = (agent_error or "").lower()
                if "api key" in lowered or "not configured" in lowered:
                    yield append_visible(
                        "\n\nAI-провайдер вернул ошибку авторизации. Без ключа проект не "
                        "соберётся — шаблоны отключены. Настройте провайдера и повторите запрос."
                    )
                else:
                    yield append_visible(f"\n\nАгент столкнулся с ошибкой: {agent_error}")

        try:
            if not api_key:
                raise _StopDeployment
            yield _sse_status("verify", "Проверяю готовые файлы проекта")
            try:
                ensure_required_files(project, artifact_path)
            except ArtifactError as verify_exc:
                if workspace_has_agent_code(artifact_path, project):
                    # Keep the agent's implementation. Never wipe real code with a stub.
                    ensure_dockerfile(project, artifact_path)
                    yield append_visible(
                        f"\n\nПроверка entrypoint неполная ({verify_exc}), но код агента сохранён. "
                        "Если бот ведёт себя не так - напишите в чат, что поправить."
                    )
                else:
                    yield _sse_status("verify", "Не хватает файлов проекта", "error")
                    yield append_visible(
                        f"\n\nАгент не создал обязательные файлы ({verify_exc}). "
                        "Шаблон не подставляется — опишите задачу ещё раз или уточните, что "
                        "нужно дописать, и агент соберёт код с нуля."
                    )
                    raise _StopDeployment
            for rel_path in _generated_files(artifact_path):
                yield _sse_status("module", f"В проекте: {rel_path}")
            thin_arch = thin_bot_architecture_warning(artifact_path, project)
            if thin_arch:
                yield _sse_status("verify", "Архитектура выглядит слишком тонкой", "error")
                yield append_visible(f"\n\n{thin_arch}")
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
                project.logs = f"Generated artifact: {artifact_path}\nGit commit: {git_commit_hash}"
            elif not project.logs:
                project.logs = f"Generated artifact: {artifact_path}"
            db.add(project)
            has_website = project.type in ("website", "mixed")
            has_bot = project.type in ("telegram_bot", "mixed")
            if reconcile_type_with_workspace(project, artifact_path):
                has_website = project.type in ("website", "mixed")
                has_bot = project.type in ("telegram_bot", "mixed")
                db.add(project)
            if has_bot and not _telegram_token(db, project):
                ensure_secret_placeholder(
                    db, project, "TELEGRAM_BOT_TOKEN", "Нужен для запуска Telegram-бота"
                )
                project.status = "needs_configuration"
                if "TELEGRAM_BOT_TOKEN" in requested_secret_keys:
                    # Already explained above (agent called request_secret this turn) -
                    # avoid repeating the same instructions twice in one reply.
                    token_note = "Запуск отложен до заполнения токена."
                else:
                    token_help_url = (
                        f"{settings.resolved_frontend_url}/help/telegram-token"
                        f"?projectId={project.id}"
                    )
                    token_note = (
                        "Entrypoint бота (app.py) на месте, но запуск остановлен: добавьте секрет "
                        "TELEGRAM_BOT_TOKEN в настройках проекта и повторите запуск.\n\n"
                        "Как получить токен: откройте @BotFather в Telegram, выполните /newbot "
                        f"и скопируйте выданный token. [Подробная инструкция]({token_help_url})"
                    )
                project.logs = f"{project.logs}\n{token_note}".strip()
                db.add(project)
                yield _sse_status("needs_configuration", "Нужен TELEGRAM_BOT_TOKEN", "error")
                yield append_visible(f"\n\n{token_note}")
                raise _StopDeployment
            if has_website and has_bot:
                yield _sse_status("deploy", "Ставлю сайт и бота в очередь запуска", "running")
                deployment, limit_message = _queue_deployment_or_notify_limit(db, project)
            elif has_website and settings.auto_deploy_websites:
                yield _sse_status("deploy", "Ставлю сайт в очередь запуска", "running")
                deployment, limit_message = _queue_deployment_or_notify_limit(db, project)
            elif has_bot:
                yield _sse_status("deploy", "Ставлю бота в очередь запуска", "running")
                deployment, limit_message = _queue_deployment_or_notify_limit(db, project)
            else:
                deployment, limit_message = None, None

            if limit_message:
                yield _sse_status("limit", limit_message, "error")
                yield append_visible(f"\n\n{limit_message}")
            elif deployment is not None:
                last_label = ""
                watched_id = deployment.id
                deadline = time.monotonic() + _DEPLOY_WAIT_SECONDS

                # Emit an immediate status from the current row (sync path may already be done).
                db.refresh(deployment)
                label = _deploy_status_label(deployment.status)
                if label != last_label:
                    state = (
                        "done"
                        if deployment.status == "completed"
                        else "error"
                        if deployment.status == "failed"
                        else "running"
                    )
                    yield _sse_status("deploy", label, state)
                    last_label = label

                if deployment.status not in _DEPLOYMENT_TERMINAL:
                    while time.monotonic() < deadline:
                        await asyncio.sleep(_DEPLOY_POLL_SECONDS)
                        db.expire_all()
                        deployment = db.get(Deployment, watched_id)
                        if deployment is None:
                            break
                        label = _deploy_status_label(deployment.status)
                        if label != last_label:
                            state = (
                                "done"
                                if deployment.status == "completed"
                                else "error"
                                if deployment.status == "failed"
                                else "running"
                            )
                            yield _sse_status("deploy", label, state)
                            last_label = label
                        if deployment.status in _DEPLOYMENT_TERMINAL:
                            break

                db.expire_all()
                db.refresh(project)
                if deployment is not None:
                    db.refresh(deployment)

                # If the first deploy looked successful, wait for post-deploy auto-check /
                # possible repair redeploy before celebrating in chat.
                if (
                    deployment is not None
                    and deployment.status == "completed"
                    and project.status == "live"
                ):
                    await asyncio.sleep(_DEPLOY_SETTLE_SECONDS)
                    db.expire_all()
                    db.refresh(project)
                    newer = (
                        db.query(Deployment)
                        .filter(
                            Deployment.project_id == project.id,
                            Deployment.id != watched_id,
                        )
                        .order_by(Deployment.started_at.desc().nullslast())
                        .first()
                    )
                    if newer is not None and newer.started_at is not None:
                        watched = db.get(Deployment, watched_id)
                        if watched and watched.started_at and newer.started_at >= watched.started_at:
                            if newer.status not in _DEPLOYMENT_TERMINAL:
                                yield _sse_status(
                                    "deploy",
                                    "Проверяю запуск и при необходимости пересобираю",
                                    "running",
                                )
                                while time.monotonic() < deadline:
                                    await asyncio.sleep(_DEPLOY_POLL_SECONDS)
                                    db.expire_all()
                                    newer = db.get(Deployment, newer.id)
                                    if newer is None:
                                        break
                                    label = _deploy_status_label(newer.status)
                                    if label != last_label:
                                        state = (
                                            "done"
                                            if newer.status == "completed"
                                            else "error"
                                            if newer.status == "failed"
                                            else "running"
                                        )
                                        yield _sse_status("deploy", label, state)
                                        last_label = label
                                    if newer.status in _DEPLOYMENT_TERMINAL:
                                        break
                            if newer is not None:
                                deployment = newer
                                watched_id = newer.id
                    db.expire_all()
                    db.refresh(project)
                    if deployment is not None:
                        db.refresh(deployment)

                if (
                    deployment is not None
                    and deployment.status == "completed"
                    and project.status == "live"
                ):
                    yield append_visible(
                        _launch_success_message(
                            project, has_website=has_website, has_bot=has_bot
                        )
                    )
                    yield _sse_status("done", "Проект запущен и работает", "done")
                elif deployment is not None and deployment.status == "failed":
                    yield append_visible(_launch_failure_message(deployment, project))
                    yield _sse_status("error", "Запуск не удался", "error")
                elif deployment is not None and deployment.status in {"cancelled", "stopped"}:
                    yield append_visible("\n\nЗапуск остановлен.")
                    yield _sse_status("error", "Запуск остановлен", "error")
                else:
                    # Still queued/running past the wait window - fail the row so UI can't stick.
                    if deployment is not None and deployment.status not in _DEPLOYMENT_TERMINAL:
                        deployment.status = "failed"
                        store_deployment_error(
                            deployment,
                            f"Timed out waiting for deployment after {_DEPLOY_WAIT_SECONDS}s",
                        )
                        deployment.finished_at = datetime.now(UTC)
                        db.add(deployment)
                        if project.status == "deploying":
                            project.status = "ready"
                            note = f"Deployment timed out in chat wait: {deployment.id}"
                            project.logs = (
                                f"{project.logs}\n{note}".strip() if project.logs else note
                            )
                            db.add(project)
                        db.commit()
                        yield append_visible(_launch_failure_message(deployment, project))
                        yield _sse_status("error", "Запуск не удался (таймаут)", "error")
                    else:
                        yield append_visible(
                            "\n\nЗапуск ещё не завершён. Итог смотрите во вкладках «Деплои» и «Логи» — "
                            "сообщение «запущено» появится только когда контейнер реально станет live."
                        )
                        yield _sse_status("deploy", "Запуск ещё идёт", "running")
            elif has_website or has_bot:
                # Queued path requested but no deployment object (shouldn't happen without limit).
                yield _sse_status("error", "Не удалось поставить деплой в очередь", "error")
            else:
                yield _sse_status("done", "Файлы сохранены", "done")
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
        record_usage(db, current_user, project_id=project.id, amount=usage_cost)
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
        provider_override=payload.provider,
        model_override=payload.model,
    )


@router.post("/{chat_id}/repair-stream")
async def stream_repair_post(
    project_id: UUID,
    chat_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Run check-and-repair with the same live SSE status/chunks as a normal chat turn."""
    from src.services.deployment_check import iter_repair_sse

    project, chat = _authorize_chat(db, project_id, chat_id, current_user)
    if current_user.credits_balance <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits"
        )

    async def event_source():
        async for frame in iter_repair_sse(db, project, chat):
            yield frame

    return StreamingResponse(event_source(), media_type="text/event-stream")


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
