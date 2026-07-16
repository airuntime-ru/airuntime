"""Post-deploy self-verification: fetch the running container's own logs, look for real
errors, and if found feed them back to the coding agent to fix - rather than leaving a broken
deployment for the user to notice and report back manually."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from src.db.models.deployment import Deployment
from src.db.models.project import Project
from src.services.agent.async_utils import run_async
from src.services.agent.events import AgentDone, TextDelta
from src.services.agent.loop import CodingAgentSession
from src.services.agent.prompt import build_runtime_repair_prompt
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


async def _run_runtime_repair(project: Project, root, error_log: str) -> str:
    provider_name, model, api_key = _resolve_provider_and_key()
    if not api_key:
        raise ArtifactError("No AI provider key configured for automatic repair")

    workspace = WorkspaceTools(root, project_id=str(project.id))
    session = CodingAgentSession(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        workspace=workspace,
        system_prompt=build_runtime_repair_prompt(project, error_log),
    )
    user_message = "Проверь и исправь ошибку из runtime-логов выше."
    final_text = ""
    async for event in session.run(history=[], user_message=user_message):
        if isinstance(event, TextDelta):
            final_text += event.text
        elif isinstance(event, AgentDone) and event.reason == "error":
            raise ArtifactError(f"AI repair failed: {event.error}")
    return final_text


def check_and_repair_deployment(db: Session, project: Project) -> dict:
    """Fetch the current deployment's runtime logs, and if they show a real error, have the
    agent fix it and queue a redeploy. Safe to call repeatedly - a clean deployment is a no-op."""
    deployment = (
        db.query(Deployment)
        .filter(Deployment.project_id == project.id, Deployment.status == "completed")
        .order_by(Deployment.finished_at.desc().nullslast(), Deployment.started_at.desc())
        .first()
    )
    if not deployment or not deployment.container_id:
        return {
            "checked": False,
            "found_errors": False,
            "fixed": False,
            "summary": "Нет запущенного деплоя для проверки.",
        }

    result = submit_control_job(
        action="logs",
        project_id=str(project.id),
        extra={"container_id": deployment.container_id, "tail": 300},
    )
    if result is None or not result.get("ok"):
        return {
            "checked": False,
            "found_errors": False,
            "fixed": False,
            "summary": "Не удалось получить логи контейнера для проверки.",
        }

    error_excerpt = detect_runtime_errors(result.get("logs", ""))
    if not error_excerpt:
        return {
            "checked": True,
            "found_errors": False,
            "fixed": False,
            "summary": "Ошибок в логах не найдено - деплой выглядит исправным.",
        }

    root = _project_dir(project.id)
    try:
        summary = run_async(_run_runtime_repair(project, root, error_excerpt))
        ensure_required_files(project, root)
    except ArtifactError as exc:
        return {
            "checked": True,
            "found_errors": True,
            "fixed": False,
            "summary": f"Найдена ошибка в логах, но автоисправление не удалось: {exc}",
        }

    _write_manifest(project, root, source="runtime-repair")
    try:
        commit_snapshot(root, message=f"Автоисправление после проверки деплоя: {project.name}")
    except Exception:  # noqa: BLE001 - git snapshotting is best-effort
        pass

    from src.services.deployments import create_deployment_for_project

    # skip_auto_check=True: this redeploy is itself the result of a check - don't chain another
    # automatic check-and-repair cycle after it lands, to bound this to one repair attempt.
    create_deployment_for_project(db, project, skip_auto_check=True)

    clean_summary = summary.strip() or "исправлена ошибка из runtime-логов"
    note = f"Автопроверка деплоя нашла и исправила ошибку: {clean_summary}"
    project.logs = f"{project.logs}\n{note}".strip() if project.logs else note
    db.add(project)
    db.commit()

    return {"checked": True, "found_errors": True, "fixed": True, "summary": clean_summary}
