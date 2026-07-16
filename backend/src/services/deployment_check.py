"""Post-deploy self-verification and failed-deploy repair.

Fetches container logs (or the deployment error text when the job never got a
container) and feeds real errors back to the coding agent to fix and redeploy.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from src.db.models.chat import Chat
from src.db.models.deployment import Deployment
from src.db.models.message import Message
from src.db.models.project import Project
from src.services.agent.async_utils import run_async
from src.services.agent.events import AgentDone, TextDelta
from src.services.agent.loop import CodingAgentSession
from src.services.agent.prompt import build_repair_prompt, build_runtime_repair_prompt
from src.services.agent.tools import WorkspaceTools
from src.services.agentic_artifacts import (
    _resolve_provider_and_key,
    _write_manifest,
    ensure_required_files,
)
from src.services.artifacts import ArtifactError
from src.services.docker_control_queue import submit_control_job
from src.services.project_git import commit_snapshot
from src.services.workspace import project_dir as _project_dir

_ERROR_PATTERNS = (
    re.compile(r"Traceback \(most recent call last\):"),
    re.compile(r"\bCRITICAL\b"),
    re.compile(r"\bERROR\b.{0,200}(Error|Exception)"),
    re.compile(r"^\S+Error: ", re.MULTILINE),
    re.compile(r"^\S+Exception: ", re.MULTILINE),
)

_BUILD_HINTS = (
    "docker",
    "build failed",
    "dockerfile",
    "pip install",
    "requirements.txt",
    "no module named",
    "pg_config",
    "error building",
)


def detect_runtime_errors(logs: str) -> str | None:
    """Returns a relevant excerpt around the first error match, or None if the log looks clean.
    Deliberately narrow patterns (real tracebacks/exceptions) to avoid false positives on
    ordinary INFO/DEBUG lines that happen to contain the word "error" in prose."""
    if not logs:
        return None
    for pattern in _ERROR_PATTERNS:
        match = pattern.search(logs)
        if match:
            start = max(0, match.start() - 500)
            return logs[start:]
    return None


def _looks_like_build_failure(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in _BUILD_HINTS)


def _latest_checkable_deployment(db: Session, project: Project) -> Deployment | None:
    return (
        db.query(Deployment)
        .filter(
            Deployment.project_id == project.id,
            Deployment.status.in_(("completed", "failed")),
        )
        .order_by(Deployment.finished_at.desc().nullslast(), Deployment.started_at.desc())
        .first()
    )


def _collect_error_excerpt(
    deployment: Deployment | None, *, force_error: str | None = None
) -> tuple[str | None, bool]:
    """Returns (error_excerpt, from_build_failure)."""
    if force_error and force_error.strip():
        return force_error.strip()[:8000], _looks_like_build_failure(force_error)

    if not deployment:
        return None, False

    # Failed jobs often store the exception text on logs_ref before any container exists.
    if deployment.status == "failed" and deployment.logs_ref:
        text = deployment.logs_ref.strip()
        if text:
            return text[:8000], _looks_like_build_failure(text)

    if deployment.container_id:
        result = submit_control_job(
            action="logs",
            project_id=str(deployment.project_id),
            extra={"container_id": deployment.container_id, "tail": 400},
        )
        if result and result.get("ok"):
            runtime = detect_runtime_errors(result.get("logs", "") or "")
            if runtime:
                return runtime[:8000], False
            if deployment.status == "failed" and result.get("logs"):
                # Container existed but patterns didn't match - still give agent the tail.
                return str(result.get("logs"))[-4000:], False

    return None, False


async def _run_repair(project: Project, root, error_log: str, *, build_failure: bool) -> str:
    provider_name, model, api_key = _resolve_provider_and_key()
    if not api_key:
        raise ArtifactError("No AI provider key configured for automatic repair")

    workspace = WorkspaceTools(root, project_id=str(project.id))
    system_prompt = (
        build_repair_prompt(project)
        if build_failure
        else build_runtime_repair_prompt(project, error_log)
    )
    session = CodingAgentSession(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        workspace=workspace,
        system_prompt=system_prompt,
    )
    if build_failure:
        user_message = (
            "Деплой/сборка упали с ошибкой:\n\n"
            f"{error_log[:4000]}\n\n"
            "Исправь код и зависимости так, чтобы сборка и запуск прошли. "
            "Не спрашивай разрешения - сразу правь файлы и вызови build_project."
        )
    else:
        user_message = "Проверь и исправь ошибку из runtime-логов выше."

    final_text = ""
    async for event in session.run(history=[], user_message=user_message):
        if isinstance(event, TextDelta):
            final_text += event.text
        elif isinstance(event, AgentDone) and event.reason == "error":
            raise ArtifactError(f"AI repair failed: {event.error}")
    return final_text


def _notify_repair_started(db: Session, project: Project, summary: str) -> None:
    chat = (
        db.query(Chat)
        .filter(Chat.project_id == project.id)
        .order_by(Chat.created_at.desc())
        .first()
    )
    if not chat:
        return
    note = (
        "Нашёл ошибку запуска и пытаюсь исправить автоматически"
        + (f": {summary}" if summary else ".")
        + " После правок поставлю проект в очередь на повторный запуск."
    )
    db.add(Message(chat_id=chat.id, role="assistant", content_markdown=note))


def check_and_repair_deployment(
    db: Session,
    project: Project,
    *,
    force_error: str | None = None,
) -> dict:
    """Inspect the latest completed/failed deployment and repair if an error is found.

    Safe to call repeatedly. A clean completed deployment is a no-op. Failed deployments
    are checked via logs_ref and/or container logs, then auto-fixed and redeployed once.
    """
    deployment = _latest_checkable_deployment(db, project)
    if not deployment and not force_error:
        return {
            "checked": False,
            "found_errors": False,
            "fixed": False,
            "summary": "Нет деплоя для проверки (ни успешного, ни упавшего).",
        }

    error_excerpt, build_failure = _collect_error_excerpt(deployment, force_error=force_error)

    if not error_excerpt:
        if deployment and deployment.status == "failed":
            return {
                "checked": True,
                "found_errors": True,
                "fixed": False,
                "summary": (
                    "Деплой упал, но детальный лог ошибки недоступен. "
                    "Нажмите «Собрать и запустить» или опишите проблему в чате."
                ),
            }
        return {
            "checked": True,
            "found_errors": False,
            "fixed": False,
            "summary": "Ошибок в логах не найдено - деплой выглядит исправным.",
        }

    root = _project_dir(project.id)
    try:
        summary = run_async(
            _run_repair(project, root, error_excerpt, build_failure=build_failure)
        )
        ensure_required_files(project, root)
    except ArtifactError as exc:
        return {
            "checked": True,
            "found_errors": True,
            "fixed": False,
            "summary": f"Найдена ошибка, но автоисправление не удалось: {exc}",
        }

    _write_manifest(project, root, source="deploy-repair")
    try:
        commit_snapshot(root, message=f"Автоисправление после ошибки деплоя: {project.name}")
    except Exception:  # noqa: BLE001 - git snapshotting is best-effort
        pass

    from src.services.deployments import create_deployment_for_project

    # skip_auto_check=True: this redeploy is itself the result of a check - don't chain another
    # automatic check-and-repair cycle after it lands, to bound this to one repair attempt.
    try:
        create_deployment_for_project(db, project, skip_auto_check=True)
    except Exception as exc:  # noqa: BLE001 - still report that code was fixed
        return {
            "checked": True,
            "found_errors": True,
            "fixed": True,
            "summary": (
                f"Код исправлен ({summary.strip() or 'правки применены'}), "
                f"но повторный запуск не удалось поставить в очередь: {exc}"
            ),
        }

    clean_summary = summary.strip() or "исправлена ошибка деплоя"
    note = f"Автопроверка деплоя нашла и исправила ошибку: {clean_summary}"
    project.logs = f"{project.logs}\n{note}".strip() if project.logs else note
    db.add(project)
    _notify_repair_started(db, project, clean_summary)
    db.commit()

    return {"checked": True, "found_errors": True, "fixed": True, "summary": clean_summary}
