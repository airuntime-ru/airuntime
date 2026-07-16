"""Workspace tools exposed to the coding agent.

Deliberately small and explicit (per the platform's security architecture:
"LLM tool execution allowlist - explicitly registered tools only"). There is
no generic shell/exec tool here: the model can inspect and edit files, and
separately the build/test step (src/services/artifacts.py) actually builds
the project in Docker and reports back real errors. Keeping "edit" and
"execute" as separate stages keeps the blast radius of a single tool call
small and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.services.workspace import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    WorkspaceError,
    list_workspace_files,
    resolve_in_workspace,
    workspace_size_bytes,
)

TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "list_files",
        "description": (
            "List files that currently exist in the project workspace. Always call this "
            "before writing files so you know what already exists and avoid clobbering it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative subdirectory to list, default '.' (whole project).",
                }
            },
            "required": [],
        },
    },
    {
        "name": "read_file",
        "description": "Read the full current contents of one file in the project workspace.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative file path."}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Create a new file, or completely replace the contents of an existing file. "
            "Use this for new files or full rewrites; use edit_file for small, targeted changes "
            "to an existing file so you don't have to resend the whole file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path."},
                "content": {"type": "string", "description": "Full UTF-8 file content."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": (
            "Make a precise, incremental edit to an existing file by replacing one exact, "
            "unique occurrence of old_text with new_text. Fails if old_text is not found or "
            "is not unique in the file - in that case include more surrounding context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path."},
                "old_text": {"type": "string", "description": "Exact existing snippet to replace."},
                "new_text": {"type": "string", "description": "Replacement text."},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file from the project workspace.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative file path."}},
            "required": ["path"],
        },
    },
    {
        "name": "build_project",
        "description": (
            "Build a real Docker image from the project's current files right now, so you can "
            "see actual build errors (missing dependency, syntax error, wrong path, bad base "
            "image, etc.) and fix them yourself before ending your turn - instead of only "
            "finding out after the automatic build attempt that happens once you're done. Can "
            "take up to a few minutes (base image pulls). Call it once your files are ready to "
            "try, read the returned log, and keep fixing + rebuilding until it succeeds or "
            "you're confident the remaining issue needs the user's input (e.g. a missing "
            "secret)."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "request_secret",
        "description": (
            "Ask the platform to reserve a secret slot (API key, token, credential) that this "
            "project's code will read from an environment variable. This does NOT ask the user "
            "for the value in chat - it creates an empty, named slot that the user fills in "
            "themselves in the project's Settings page, where the platform can validate it. "
            "Call this as soon as you know the project needs a credential you don't have, "
            "instead of asking for it as chat text and instead of inventing/hardcoding a value. "
            "Safe to call again for the same key - it won't overwrite an existing value.\n"
            "IMPORTANT - do NOT use this for a database/cache/queue that YOU are provisioning "
            "for this project (e.g. a key named DATABASE_URL, REDIS_URL, MONGO_URL, "
            "RABBITMQ_URL for a service you're about to create) - call request_service for "
            "that instead, which provisions the real container and injects the connection "
            "string automatically. Never make a non-technical user manually type a connection "
            "string for infrastructure the platform can just set up for them. Only use "
            "request_secret for things you genuinely cannot provision yourself: a third-party "
            "API key, a payment gateway secret, or a database/service the user explicitly says "
            "they already have elsewhere and will connect to."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": (
                        "UPPER_SNAKE_CASE environment variable name the code reads, e.g. "
                        "TELEGRAM_BOT_TOKEN or STRIPE_SECRET_KEY."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": "One short sentence shown to the user explaining what it's for.",
                },
            },
            "required": ["key", "reason"],
        },
    },
    {
        "name": "request_service",
        "description": (
            "Ask the platform to provision a real backing service (database, cache, queue, "
            "search index - anything that runs as its own container) for this project, when "
            "SQLite genuinely isn't enough. Call this instead of writing a docker-compose.yml "
            "or assuming an external service already exists - the platform starts the "
            "container for you on a private network reachable from your app. For "
            "'postgres'/'redis'/'mysql'/'mongo'/'rabbitmq', just pass kind - the platform picks "
            "a sensible image, generates credentials, and injects a ready connection-string env "
            "var (DATABASE_URL/REDIS_URL/MONGO_URL/RABBITMQ_URL) your code should read, not "
            "invent. For anything else (Elasticsearch, ClickHouse, a Celery worker built from "
            "this same project's own Dockerfile, or any other image), pass kind as a short "
            "label plus `image` explicitly - the tool result tells you the exact hostname to "
            "connect to; use that hostname with whatever port/credentials you configure via "
            "`env`, since there's no auto-generated connection string for a custom image. Safe "
            "to call again for the same kind - it won't create a duplicate or change an "
            "existing service's config. This is the only correct way to give the project a "
            "database/cache/queue it doesn't already have - never ask the user (via "
            "request_secret or chat text) to supply a connection string for something you're "
            "provisioning yourself; most users aren't technical and won't know what that means."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "description": (
                        "Short label identifying the service, e.g. postgres, redis, rabbitmq, "
                        "search, worker. Used to build its hostname/container name."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": "One short sentence: why this project needs it.",
                },
                "image": {
                    "type": "string",
                    "description": (
                        "Docker image to run, e.g. 'elasticsearch:8.15.0' or "
                        "'rabbitmq:3-management'. Required unless kind is one of the built-in "
                        "presets (postgres/redis/mysql/mongo/rabbitmq)."
                    ),
                },
                "env": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": (
                        "Extra environment variables to set on the service's own container "
                        "(its config, not your app's) - e.g. credentials or settings that "
                        "image's docs call for. Not needed for the built-in presets unless you "
                        "want to override their defaults."
                    ),
                },
                "data_path": {
                    "type": "string",
                    "description": (
                        "Absolute path inside the service's container where it stores data, "
                        "e.g. '/var/lib/rabbitmq' - the platform mounts a persistent volume "
                        "there so data survives restarts. Omit for services that don't need "
                        "persistence, or for a preset kind (already knows its own path)."
                    ),
                },
            },
            "required": ["kind", "reason"],
        },
    },
]

TOOL_NAMES = {tool["name"] for tool in TOOL_DEFS}


@dataclass
class ToolExecutionResult:
    ok: bool
    summary: str
    content: str = ""


@dataclass
class ServiceRequest:
    kind: str
    reason: str
    image: str | None = None
    env: dict[str, str] | None = None
    data_path: str | None = None


class WorkspaceTools:
    """Executes agent tool calls against one project's workspace directory."""

    def __init__(self, root: Path, *, project_id: str | None = None) -> None:
        self.root = root
        self.project_id = project_id
        self.touched_files: set[str] = set()
        self.requested_secrets: list[tuple[str, str]] = []
        self.requested_services: list[ServiceRequest] = []

    def call(self, name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        try:
            if name == "list_files":
                return self._list_files(arguments.get("path", "."))
            if name == "read_file":
                return self._read_file(str(arguments.get("path", "")))
            if name == "write_file":
                return self._write_file(
                    str(arguments.get("path", "")), arguments.get("content", "")
                )
            if name == "edit_file":
                return self._edit_file(
                    str(arguments.get("path", "")),
                    arguments.get("old_text", ""),
                    arguments.get("new_text", ""),
                )
            if name == "delete_file":
                return self._delete_file(str(arguments.get("path", "")))
            if name == "build_project":
                return self._build_project()
            if name == "request_secret":
                return self._request_secret(
                    str(arguments.get("key", "")), str(arguments.get("reason", ""))
                )
            if name == "request_service":
                return self._request_service(
                    str(arguments.get("kind", "")),
                    str(arguments.get("reason", "")),
                    image=arguments.get("image"),
                    env=arguments.get("env"),
                    data_path=arguments.get("data_path"),
                )
            return ToolExecutionResult(ok=False, summary=f"Unknown tool: {name}")
        except WorkspaceError as exc:
            return ToolExecutionResult(ok=False, summary=str(exc))
        except Exception as exc:  # defensive: never let a tool crash the agent loop
            return ToolExecutionResult(ok=False, summary=f"Tool error: {exc}")

    def _list_files(self, path: str) -> ToolExecutionResult:
        if path and path != ".":
            base = resolve_in_workspace(self.root, path)
            if not base.exists():
                return ToolExecutionResult(
                    ok=True, summary="Directory does not exist yet.", content="[]"
                )
            files = [
                p.relative_to(self.root).as_posix()
                for p in sorted(base.rglob("*"))
                if p.is_file() and ".git" not in p.parts and ".airuntime" not in p.parts
            ]
        else:
            files = list_workspace_files(self.root)
        content = "\n".join(files) if files else "(empty workspace)"
        return ToolExecutionResult(ok=True, summary=f"{len(files)} file(s)", content=content)

    def _read_file(self, path: str) -> ToolExecutionResult:
        target = resolve_in_workspace(self.root, path)
        if not target.exists() or not target.is_file():
            return ToolExecutionResult(ok=False, summary=f"File not found: {path}")
        data = target.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            return ToolExecutionResult(
                ok=False, summary=f"File is too large to read ({len(data)} bytes)"
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return ToolExecutionResult(ok=False, summary="File is not valid UTF-8 text")
        return ToolExecutionResult(
            ok=True, summary=f"Read {path} ({len(data)} bytes)", content=text
        )

    def _write_file(self, path: str, content: Any) -> ToolExecutionResult:
        if not isinstance(content, str):
            return ToolExecutionResult(ok=False, summary="content must be a string")
        target = resolve_in_workspace(self.root, path)
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            return ToolExecutionResult(ok=False, summary=f"File too large ({len(encoded)} bytes)")
        current_total = workspace_size_bytes(self.root)
        existing = target.stat().st_size if target.exists() else 0
        if current_total - existing + len(encoded) > MAX_TOTAL_BYTES:
            return ToolExecutionResult(ok=False, summary="Project workspace size limit exceeded")
        existing_files = set(list_workspace_files(self.root))
        rel = target.relative_to(self.root).as_posix()
        if rel not in existing_files and len(existing_files) >= MAX_FILES:
            return ToolExecutionResult(
                ok=False, summary=f"Too many files in project (max {MAX_FILES})"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.touched_files.add(rel)
        return ToolExecutionResult(ok=True, summary=f"Wrote {rel} ({len(encoded)} bytes)")

    def _edit_file(self, path: str, old_text: Any, new_text: Any) -> ToolExecutionResult:
        if not isinstance(old_text, str) or not old_text:
            return ToolExecutionResult(ok=False, summary="old_text must be a non-empty string")
        if not isinstance(new_text, str):
            return ToolExecutionResult(ok=False, summary="new_text must be a string")
        target = resolve_in_workspace(self.root, path)
        if not target.exists():
            return ToolExecutionResult(
                ok=False, summary=f"File not found: {path}. Use write_file to create it first."
            )
        current = target.read_text(encoding="utf-8")
        count = current.count(old_text)
        if count == 0:
            return ToolExecutionResult(
                ok=False,
                summary="old_text not found in file - re-read the file, it may have changed",
            )
        if count > 1:
            return ToolExecutionResult(
                ok=False,
                summary=f"old_text is not unique ({count} occurrences) - include more context",
            )
        updated = current.replace(old_text, new_text, 1)
        encoded = updated.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            return ToolExecutionResult(ok=False, summary="Resulting file would be too large")
        target.write_text(updated, encoding="utf-8")
        rel = target.relative_to(self.root).as_posix()
        self.touched_files.add(rel)
        return ToolExecutionResult(ok=True, summary=f"Edited {rel}")

    def _build_project(self) -> ToolExecutionResult:
        if not self.project_id:
            return ToolExecutionResult(
                ok=False, summary="Build tool unavailable outside a project context"
            )
        from src.services.docker_control_queue import submit_control_job

        result = submit_control_job(
            action="build_check", project_id=self.project_id, timeout_seconds=180
        )
        if result is None:
            return ToolExecutionResult(
                ok=False, summary="Build service did not respond - try again"
            )
        log = result.get("log", "")
        if result.get("ok"):
            return ToolExecutionResult(ok=True, summary="Build succeeded", content=log)
        return ToolExecutionResult(ok=False, summary="Build failed", content=log)

    def _request_secret(self, key: str, reason: str) -> ToolExecutionResult:
        key = key.strip()
        if not key:
            return ToolExecutionResult(ok=False, summary="key must not be empty")
        self.requested_secrets.append((key, reason.strip()))
        return ToolExecutionResult(
            ok=True,
            summary=f"Requested secret {key} - the user will fill in the value in Settings",
        )

    def _request_service(
        self,
        kind: str,
        reason: str,
        *,
        image: Any = None,
        env: Any = None,
        data_path: Any = None,
    ) -> ToolExecutionResult:
        from src.services.project_services import (
            container_name_for,
            is_known_preset,
            normalize_service_kind,
        )

        normalized_kind = normalize_service_kind(kind)
        resolved_image = image.strip() if isinstance(image, str) and image.strip() else None
        if not resolved_image and not is_known_preset(normalized_kind):
            return ToolExecutionResult(
                ok=False,
                summary=(
                    f"Unknown service kind '{normalized_kind}' - call again with an explicit "
                    "image, e.g. image='elasticsearch:8.15.0'"
                ),
            )
        resolved_env = env if isinstance(env, dict) else None
        resolved_data_path = (
            data_path.strip() if isinstance(data_path, str) and data_path.strip() else None
        )

        self.requested_services.append(
            ServiceRequest(
                kind=normalized_kind,
                reason=reason.strip(),
                image=resolved_image,
                env=resolved_env,
                data_path=resolved_data_path,
            )
        )
        hostname = (
            container_name_for(self.project_id, normalized_kind)
            if self.project_id
            else normalized_kind
        )
        return ToolExecutionResult(
            ok=True,
            summary=(
                f"Requested service '{normalized_kind}' - will be reachable at host "
                f"'{hostname}' once deployed"
            ),
        )

    def _delete_file(self, path: str) -> ToolExecutionResult:
        target = resolve_in_workspace(self.root, path)
        if not target.exists():
            return ToolExecutionResult(ok=False, summary=f"File not found: {path}")
        target.unlink()
        rel = target.relative_to(self.root).as_posix()
        self.touched_files.add(rel)
        return ToolExecutionResult(ok=True, summary=f"Deleted {rel}")
