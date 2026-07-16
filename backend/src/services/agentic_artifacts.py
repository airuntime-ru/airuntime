from __future__ import annotations

import json
import re
from pathlib import Path

from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models.project import Project
from src.services.agent.async_utils import run_async
from src.services.agent.loop import CodingAgentSession
from src.services.agent.prompt import build_repair_prompt
from src.services.agent.tools import WorkspaceTools
from src.services.artifacts import (
    MIXED_DOCKERFILE,
    ArtifactError,
    generate_mixed_artifact,
    generate_telegram_bot_artifact,
    generate_website_artifact,
)
from src.services.provider.factory import resolve_model
from src.services.system_settings import resolve_api_key_for_provider
from src.services.workspace import project_dir as _project_dir

MANIFEST_VERSION = 2

WEBSITE_REQUIRED = "public/index.html"
TELEGRAM_REQUIRED = "app.py"

# How many times to hand a build failure back to the AI before giving up.
REPAIR_ATTEMPTS = 5

_DEFAULT_WEBSITE_DOCKERFILE = "FROM nginx:1.27-alpine\nCOPY public/ /usr/share/nginx/html/\n"
_DEFAULT_TELEGRAM_DOCKERFILE = "\n".join(
    [
        "FROM python:3.12-slim",
        "WORKDIR /app",
        "COPY requirements.txt .",
        "RUN pip install --no-cache-dir -r requirements.txt",
        "COPY . .",
        'CMD ["python", "app.py"]',
        "",
    ]
)

_STUB_MARKERS = (
    "временная заглушка платформы",
    "передам его в рабочий сценарий проекта",
    "режим заглушки",
)


_TOKEN_ENV_RE = re.compile(
    r"TELEGRAM_BOT_TOKEN|getenv\(\s*[\"']TELEGRAM_BOT_TOKEN|environ(?:\.get)?\(\s*[\"']TELEGRAM_BOT_TOKEN"
)


def _resolve_provider_and_key(provider_name: str | None = None) -> tuple[str, str, str]:
    name = provider_name or settings.provider_name
    model = resolve_model(name)
    key_field = f"{name}_api_key"
    api_key = resolve_api_key_for_provider(name) or getattr(settings, key_field, None) or ""
    return name, model, api_key


def _write_manifest(project: Project, root: Path, *, source: str) -> None:
    meta_dir = root / ".airuntime"
    meta_dir.mkdir(exist_ok=True)
    from src.services.workspace import list_workspace_files

    (meta_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": MANIFEST_VERSION,
                "source": source,
                "project_id": str(project.id),
                "project_type": project.type,
                "files": list_workspace_files(root),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def workspace_has_agent_code(root: Path, project: Project) -> bool:
    """True when the agent already wrote real project files we must not wipe with a stub."""
    needs_website = project.type in ("website", "mixed")
    needs_bot = project.type in ("telegram_bot", "mixed")

    if needs_bot and (root / TELEGRAM_REQUIRED).exists():
        text = (root / TELEGRAM_REQUIRED).read_text(encoding="utf-8", errors="ignore")
        if not any(marker in text for marker in _STUB_MARKERS) and len(text.strip()) > 80:
            return True
        # Multi-module bot: entrypoint may be thin, other files hold logic.
        py_files = [p for p in root.rglob("*.py") if ".airuntime" not in p.parts]
        if len(py_files) > 1 and not any(marker in text for marker in _STUB_MARKERS):
            return True

    if needs_website and (root / WEBSITE_REQUIRED).exists():
        text = (root / WEBSITE_REQUIRED).read_text(encoding="utf-8", errors="ignore")
        if len(text.strip()) > 40:
            return True

    return False


def _reads_telegram_token(root: Path) -> bool:
    for path in root.rglob("*.py"):
        if ".airuntime" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _TOKEN_ENV_RE.search(text):
            return True
    return False


def ensure_dockerfile(project: Project, root: Path) -> bool:
    """Write a default Dockerfile if missing. Returns True when a file was created."""
    dockerfile = root / "Dockerfile"
    if dockerfile.exists():
        return False
    needs_website = project.type in ("website", "mixed")
    needs_bot = project.type in ("telegram_bot", "mixed")
    if needs_website and needs_bot:
        dockerfile.write_text(MIXED_DOCKERFILE, encoding="utf-8")
    elif needs_website:
        dockerfile.write_text(_DEFAULT_WEBSITE_DOCKERFILE, encoding="utf-8")
    else:
        dockerfile.write_text(_DEFAULT_TELEGRAM_DOCKERFILE, encoding="utf-8")
    return True


def ensure_required_files(project: Project, root: Path) -> None:
    """Fill in a default Dockerfile if missing; raise if a required entry file is missing.

    Does not force a Telegram framework (aiogram / python-telegram-bot / …) — only the
    platform entrypoint contract: app.py + token from env + requirements.txt present.
    """

    needs_website = project.type in ("website", "mixed")
    needs_bot = project.type in ("telegram_bot", "mixed")
    if not needs_website and not needs_bot:
        raise ArtifactError(f"Unsupported project type: {project.type}")

    if needs_website and not (root / WEBSITE_REQUIRED).exists():
        raise ArtifactError(
            f"Agent did not produce the required {WEBSITE_REQUIRED} - website has no content"
        )

    if needs_bot:
        if not (root / TELEGRAM_REQUIRED).exists():
            raise ArtifactError(
                f"Agent did not produce the required {TELEGRAM_REQUIRED} - bot has no code"
            )
        if not _reads_telegram_token(root):
            raise ArtifactError(
                "Bot code must read TELEGRAM_BOT_TOKEN from the environment "
                "(os.environ / os.getenv)"
            )
        requirements_path = root / "requirements.txt"
        if not requirements_path.exists():
            raise ArtifactError(
                "requirements.txt is missing - list the bot framework and other dependencies"
            )

    ensure_dockerfile(project, root)


def generate_fallback_artifact(db: Session, project: Project, prompt: str = "") -> Path:
    """Deterministic, non-AI template. Last-resort only when the workspace has no agent code."""

    if project.type == "website":
        path = generate_website_artifact(project, prompt)
    elif project.type == "telegram_bot":
        path = generate_telegram_bot_artifact(project, prompt)
    elif project.type == "mixed":
        path = generate_mixed_artifact(project, prompt)
    else:
        raise ArtifactError(f"Unsupported project type: {project.type}")

    _write_manifest(project, path, source="fallback-template")
    return path


def repair_artifact_with_fallback(db: Session, project: Project, reason: str) -> Path:
    prompt = ""
    last_prompt = _project_dir(project.id) / ".airuntime" / "last_prompt.txt"
    if last_prompt.exists():
        prompt = last_prompt.read_text(encoding="utf-8")
    path = generate_fallback_artifact(db, project, prompt)
    note = f"Artifact repaired with fallback template after build failure: {reason[:800]}"
    project.logs = f"{project.logs}\n{note}".strip() if project.logs else note
    db.add(project)
    return path


async def _run_agent_repair(project: Project, root: Path, build_error: str) -> str:
    provider_name, model, api_key = _resolve_provider_and_key()
    if not api_key:
        raise ArtifactError("No AI provider key configured for automatic repair")

    workspace = WorkspaceTools(root, project_id=str(project.id))
    session = CodingAgentSession(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        workspace=workspace,
        system_prompt=build_repair_prompt(project),
    )
    user_message = (
        "Сборка Docker-образа этого проекта упала с ошибкой:\n\n"
        f"{build_error[:4000]}\n\n"
        "Найди причину, прочитай нужные файлы и исправь их так, чтобы сборка прошла. "
        "Не заменяй проект шаблоном и не удаляй реализованную логику пользователя."
    )
    final_text = ""
    from src.services.agent.events import AgentDone, TextDelta

    async for event in session.run(history=[], user_message=user_message):
        if isinstance(event, TextDelta):
            final_text += event.text
        elif isinstance(event, AgentDone) and event.reason == "error":
            raise ArtifactError(f"AI repair failed: {event.error}")
    return final_text


def repair_artifact_with_agent(db: Session, project: Project, build_error: str) -> Path:
    """Feed the real Docker build error back to the coding agent and let it patch the
    specific files that are broken, instead of throwing the whole project away."""

    root = _project_dir(project.id)
    summary = run_async(_run_agent_repair(project, root, build_error))
    ensure_required_files(project, root)
    _write_manifest(project, root, source="ai-repair")
    note = f"AI repair: {summary.strip()}" if summary.strip() else "AI repair applied"
    project.logs = f"{project.logs}\n{note}".strip() if project.logs else note
    db.add(project)
    return root
