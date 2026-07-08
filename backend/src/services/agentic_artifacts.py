from __future__ import annotations

import json
import re
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models.project import Project
from src.services.artifacts import (
    ArtifactError,
    _telegram_token,
    generate_telegram_bot_artifact,
    generate_website_artifact,
)
from src.services.provider.factory import get_provider, resolve_model

MAX_FILES = 40
MAX_FILE_BYTES = 220_000
MAX_TOTAL_BYTES = 900_000
MANIFEST_VERSION = 1

BLOCKED_PARTS = {
    "",
    ".",
    "..",
    ".env",
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
}

WEBSITE_REQUIRED = "public/index.html"
TELEGRAM_REQUIRED = "app.py"


async def _collect_stream(stream: AsyncIterator[str]) -> str:
    chunks: list[str] = []
    async for chunk in stream:
        chunks.append(chunk)
    return "".join(chunks)


def _root() -> Path:
    root = Path(settings.generated_projects_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _project_dir(project_id: object) -> Path:
    safe_id = str(project_id)
    if not re.fullmatch(r"[a-fA-F0-9-]{32,36}", safe_id):
        raise ArtifactError("Invalid project id for artifact path")
    path = _root() / safe_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean_project_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _extract_json(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    if not fenced:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ArtifactError("AI did not return a JSON artifact manifest")
        candidate = candidate[start : end + 1]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"AI artifact manifest is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ArtifactError("AI artifact manifest must be an object")
    return payload


def _safe_relative_path(raw_path: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ArtifactError("Generated file path is empty")
    normalized = raw_path.replace("\\", "/").strip().lstrip("/")
    if "\x00" in normalized or normalized.startswith("~"):
        raise ArtifactError(f"Unsafe generated file path: {raw_path}")
    parts = normalized.split("/")
    if any(part in BLOCKED_PARTS for part in parts):
        raise ArtifactError(f"Blocked generated file path: {raw_path}")
    if any(part.startswith(".") and part != ".well-known" for part in parts):
        raise ArtifactError(f"Hidden generated files are not allowed: {raw_path}")
    if not re.fullmatch(r"[A-Za-z0-9._/\-]+", normalized):
        raise ArtifactError(f"Generated file path contains unsupported characters: {raw_path}")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ArtifactError(f"Unsafe generated file path: {raw_path}")
    return path


def _validate_file_content(path: Path, content: str) -> bytes:
    if not isinstance(content, str):
        raise ArtifactError(f"Generated file {path} content must be a string")
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise ArtifactError(f"Generated file {path} is too large")
    return encoded


def _normalize_manifest(payload: dict[str, Any], project: Project) -> dict[str, str]:
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise ArtifactError("AI artifact manifest must include non-empty files array")
    if len(files) > MAX_FILES:
        raise ArtifactError(f"AI artifact manifest has too many files (max {MAX_FILES})")

    normalized: dict[str, str] = {}
    total = 0
    for item in files:
        if not isinstance(item, dict):
            raise ArtifactError("Each generated file entry must be an object")
        rel = _safe_relative_path(str(item.get("path", "")))
        encoded = _validate_file_content(rel, item.get("content", ""))
        total += len(encoded)
        if total > MAX_TOTAL_BYTES:
            raise ArtifactError("Generated project is too large")
        normalized[rel.as_posix()] = encoded.decode("utf-8")

    if project.type == "website":
        if WEBSITE_REQUIRED not in normalized:
            raise ArtifactError("Website artifact must include public/index.html")
        if "Dockerfile" not in normalized:
            normalized["Dockerfile"] = "FROM nginx:1.27-alpine\nCOPY public/ /usr/share/nginx/html/\n"
    elif project.type == "telegram_bot":
        if TELEGRAM_REQUIRED not in normalized:
            raise ArtifactError("Telegram bot artifact must include app.py")
        normalized.setdefault("requirements.txt", "python-telegram-bot==21.10\n")
        normalized.setdefault(
            "Dockerfile",
            "\n".join(
                [
                    "FROM python:3.12-slim",
                    "WORKDIR /app",
                    "COPY requirements.txt .",
                    "RUN pip install --no-cache-dir -r requirements.txt",
                    "COPY . .",
                    'CMD ["python", "app.py"]',
                    "",
                ]
            ),
        )
        app_py = normalized["app.py"]
        if "TELEGRAM_BOT_TOKEN" not in app_py:
            raise ArtifactError("Telegram bot app.py must read TELEGRAM_BOT_TOKEN from environment")
    else:
        raise ArtifactError(f"Unsupported project type: {project.type}")

    return normalized


def _write_files(project: Project, prompt: str, files: dict[str, str], *, source: str) -> Path:
    path = _project_dir(project.id)
    _clean_project_dir(path)
    for raw_path, content in files.items():
        rel = _safe_relative_path(raw_path)
        target = (path / rel).resolve()
        if not target.is_relative_to(path.resolve()):
            raise ArtifactError(f"Generated file escapes project workspace: {raw_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    meta_dir = path / ".airuntime"
    meta_dir.mkdir(exist_ok=True)
    (meta_dir / "last_prompt.txt").write_text(prompt, encoding="utf-8")
    (meta_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": MANIFEST_VERSION,
                "source": source,
                "project_id": str(project.id),
                "project_type": project.type,
                "files": sorted(files),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _artifact_prompt(project: Project, prompt: str) -> str:
    if project.type == "telegram_bot":
        target = (
            "Generate a production-ready Python Telegram bot. Use python-telegram-bot 21.x. "
            "Read the token from os.environ['TELEGRAM_BOT_TOKEN']. Include useful commands, "
            "clear user flows, helpful fallback replies, and keep it self-contained."
        )
        required = "app.py, requirements.txt"
    else:
        target = (
            "Generate a polished responsive static website. It must run behind nginx from "
            "public/index.html. Include modern CSS, accessible markup, clear content, and small "
            "vanilla JS only when it improves the experience."
        )
        required = "public/index.html, optional public/styles.css, optional public/app.js"

    return f"""
You are AIRuntime's code generation agent. Return ONLY valid JSON, no markdown.

User project:
- type: {project.type}
- name: {project.name}
- existing description: {project.description or ""}
- latest user request: {prompt}

Task:
{target}

Required files: {required}

Return this exact shape:
{{
  "summary": "short build summary",
  "files": [
    {{"path": "relative/path", "content": "full UTF-8 file content"}}
  ]
}}

Rules:
- Paths must be relative and safe.
- Do not include secrets, .env files, node_modules, binary files, or external build artifacts.
- The project must be runnable in Docker using the included Dockerfile or the platform default.
- Keep total output compact but complete.
""".strip()


async def generate_agentic_artifact(db: Session, project: Project, prompt: str = "") -> Path:
    del db
    provider = get_provider(settings.provider_name)
    model = resolve_model(settings.provider_name)
    raw = await _collect_stream(
        provider.stream(
            messages=[{"role": "user", "content": _artifact_prompt(project, prompt)}],
            model=model,
            tools=[],
        )
    )
    payload = _extract_json(raw)
    files = _normalize_manifest(payload, project)
    return _write_files(project, prompt, files, source=f"ai:{settings.provider_name}:{model}")


def generate_fallback_artifact(db: Session, project: Project, prompt: str = "") -> Path:
    if project.type == "website":
        path = generate_website_artifact(project, prompt)
    elif project.type == "telegram_bot":
        path = generate_telegram_bot_artifact(project, prompt)
    else:
        raise ArtifactError(f"Unsupported project type: {project.type}")

    meta_dir = path / ".airuntime"
    meta_dir.mkdir(exist_ok=True)
    (meta_dir / "last_prompt.txt").write_text(prompt, encoding="utf-8")
    (meta_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": MANIFEST_VERSION,
                "source": "fallback-template",
                "project_id": str(project.id),
                "project_type": project.type,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


async def generate_project_artifact_agentic(db: Session, project: Project, prompt: str = "") -> Path:
    if project.type == "telegram_bot" and not _telegram_token(db, project):
        raise ArtifactError("Telegram bot requires TELEGRAM_BOT_TOKEN secret before deployment")
    try:
        return await generate_agentic_artifact(db, project, prompt)
    except Exception as exc:
        path = generate_fallback_artifact(db, project, prompt)
        note = f"AI artifact generation fallback used: {exc}"
        project.logs = f"{project.logs}\n{note}".strip() if project.logs else note
        db.add(project)
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
