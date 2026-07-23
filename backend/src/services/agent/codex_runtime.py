"""Drives the coding agent through the OpenAI Codex CLI instead of hand-rolled provider HTTP
calls (see agent/providers.py, which this replaces for the "openai" path only).

Why: the old path was one httpx SSE call per model turn, with a manual tool-calling loop
(agent/loop.py) driving read/write/edit/build tools ourselves. Codex is a real coding agent with
its own shell + filesystem access, retry handling and context management - we just need to run
it against this project's files and translate its event stream into the same
TextDelta/ToolCallRequested/ToolCallResult/AgentDone events the rest of the app already consumes
(SSE encoding in chat.py, chat persistence, etc. are all unchanged).

Where it actually runs: the long-lived `codex` Docker service (deployment/codex/Dockerfile,
the `codex` entry in docker-compose*.yml). That container has the projects volume and the Docker
socket, so Codex can edit this project's files and build/run Docker images itself via plain
shell commands. This module is imported by the backend API process, which - by design (see
docker_control_queue.py) - never gets Docker socket access itself: it only ever talks to Redis.
The actual `docker exec` into the codex container happens in agent/codex_worker.py, imported only
by the `worker` process, which already has that access for deployments.

Two execution paths, mirroring docker_control_queue.py's own split:
- Out-of-process (interactive chat, or the manual "Проверить и исправить" endpoint - both run
  in the backend API process): push a job onto the existing docker_control_queue list
  (action="codex_run"); the worker execs into the codex container and relays each line of
  `codex exec --json` output onto a per-run Redis list as it's produced, which we poll live
  instead of blocking on one result. This is what keeps token streaming working end to end.
- In-process (an automatic repair flow already running inside the worker, under
  docker_control_queue.in_worker_inline_docker()): call agent/codex_worker.py directly instead
  of queueing. Queueing here would mean the single worker process waits on a job only it can
  service - the same self-deadlock worker_inline_docker() exists to prevent for the plain
  stop/cleanup/logs/build_check actions.

Known limitation (accepted trade-off, not a bug): the projects volume is one shared volume
across every project, and the Docker socket is unscoped - so a Codex turn for project A can
technically reach project B's files and containers. This matches the trust level the `worker`
process already had; what's new is that Codex's shell commands are chosen by a model reading
untrusted chat text, not by our own code. Tighter isolation (per-project bind mounts, a scoped
Docker proxy) is a deliberate follow-up, not part of this change.
"""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path, PurePosixPath
from typing import Any

from redis import Redis

from src.core.config import settings
from src.services.agent.events import AgentDone, TextDelta, ToolCallRequested, ToolCallResult
from src.services.agent.tools import ServiceRequest, WorkspaceTools
from src.services.docker_control_queue import QUEUE_KEY, in_worker_inline_docker
from src.services.file_context import ImageAttachment

logger = logging.getLogger(__name__)

# Providers driven through Codex instead of a direct HTTP call. Codex CLI only speaks to
# OpenAI, so this is deliberately narrow - an explicit anthropic/gemini/openrouter selection
# (by the user, or because no OpenAI key is configured) keeps using agent/providers.py.
CODEX_ELIGIBLE_PROVIDERS = {"openai"}

_EVENTS_KEY_PREFIX = "codex:events:"
_DONE_MARKER = "__codex_run_done__"
_REDIS_POLL_SECONDS = 2
# Ceiling on silence between events, not on the run overall (codex_turn_timeout_seconds is the
# overall budget). A slow step with no --json output of its own (docker build pulling a base
# image, a big pip install) can legitimately stay quiet for a few minutes - this only needs to
# catch a genuinely dead worker/container, not police pace.
_MAX_IDLE_SECONDS = 300

_CODEX_BRIDGE_INSTRUCTIONS = """\
Технически ты работаешь не через отдельные инструменты платформы, а напрямую в Linux-контейнере \
с shell и полным доступом к файлам этого проекта (текущая рабочая директория) и к Docker (сокет \
примонтирован, команда `docker` доступна). Используй обычные средства (чтение/запись файлов, \
`docker build`) вместо вызовов list_files/read_file/write_file/edit_file/build_project - таких \
инструментов здесь нет, их заменяет прямой shell-доступ. `docker run` допустим только для \
локальной проверки внутри своей работы; НЕ публикуй прод через `docker run -p`, НЕ пиши \
docker-compose.yml для маршрутизации и НЕ настраивай Traefik/прокси/домены - публичный URL и \
Traefik-labels вешает платформа после хода. Для сайтов HTTP в контейнере должен слушать порт 80.

Чтобы запросить секрет от пользователя (Telegram-токен, чужой API-ключ) - создай файл \
.airuntime/requests/secret__<KEY>.json с содержимым {"key": "<KEY>", "reason": "..."}.

Чтобы запросить служебный сервис (Postgres/Redis/...) - создай файл \
.airuntime/requests/service__<kind>.json с содержимым {"kind": "...", "reason": "...", \
"image": "...", "env": {}, "data_path": "..."} (image/env/data_path необязательны для \
стандартных kind: postgres/redis/mysql/mongo/rabbitmq).

Никогда не трогай файлы или Docker-контейнеры других проектов - работай только в своей текущей \
директории. Обычно физически ничего другого и не видно (у тебя примонтирован только этот \
проект), но не пытайся обойти это через Docker (например через `docker exec` в чужой контейнер \
по угаданному имени).

Если задача явно распадается на независимые крупные ПРОДУКТОВЫЕ куски (например: лендинг, \
личный кабинет/API, telegram-бот - части, которые не зависят от результата друг друга) и это \
ускорит работу без потери качества - можешь делегировать часть работы своим subagent'ами \
параллельно вместо последовательной работы в одиночку. Не выделяй отдельную часть про \
инфраструктуру/Traefik/деплой/сеть. Не дели ради самого деления: для большинства задач \
(один сайт, один бот) быстрее и надёжнее сделать самому последовательно.\
"""


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _events_key(run_id: str) -> str:
    return f"{_EVENTS_KEY_PREFIX}{run_id}"


def _submit_run(
    *,
    project_id: str | None,
    cwd: str | None,
    model: str,
    prompt: str,
    image_paths: list[str],
    timeout_seconds: int,
) -> str:
    run_id = uuid.uuid4().hex
    job = {
        "job_id": run_id,
        "action": "codex_run",
        "project_id": project_id,
        "cwd": cwd,
        "model": model,
        "prompt": prompt,
        "image_paths": image_paths,
        "timeout_seconds": timeout_seconds,
    }
    _redis().rpush(QUEUE_KEY, json.dumps(job))
    return run_id


async def _stream_events(run_id: str, *, timeout_seconds: int) -> AsyncIterator[dict[str, Any]]:
    """Yield decoded event dicts as the worker relays them, until a terminal marker, an
    explicit error, or a timeout. Runs the blocking Redis call off the event loop so this can
    be awaited from the async chat-streaming path without stalling other requests."""
    import asyncio

    key = _events_key(run_id)
    r = _redis()
    deadline = time.monotonic() + timeout_seconds
    idle_deadline = time.monotonic() + _MAX_IDLE_SECONDS

    while True:
        now = time.monotonic()
        if now > deadline:
            logger.warning("Codex run %s timed out after %ds", run_id, timeout_seconds)
            yield {"type": "infra_error", "message": "Codex run timed out"}
            return
        popped = await asyncio.to_thread(r.blpop, key, _REDIS_POLL_SECONDS)
        if not popped:
            if time.monotonic() > idle_deadline:
                logger.warning(
                    "Codex run %s produced no output for %ds (worker/container may be down)",
                    run_id,
                    _MAX_IDLE_SECONDS,
                )
                yield {
                    "type": "infra_error",
                    "message": "Codex produced no output for a while (worker/container may be down)",
                }
                return
            continue
        idle_deadline = time.monotonic() + _MAX_IDLE_SECONDS
        _, raw = popped
        if raw == _DONE_MARKER:
            return
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            continue


_ISOLATED_MOUNT_ROOT = PurePosixPath("/workspace")


def _relativize(path_str: str, root: Path | None) -> str:
    """Show paths relative to the project root in the UI - the raw item.path is an absolute
    in-container path, which leaks server layout for no benefit to the user.

    Two possible absolute forms reach here, and this process can't tell which one a given run
    used: codex_worker.py's per-project mount resolution succeeding remaps the path under
    /workspace (see _WORKSPACE_MOUNT there); resolution failing falls back to the original
    `{generated_projects_dir}/{project_id}` path, which matches `root` (this process's own view
    of the same directory). Try both rather than assuming - the /workspace case previously fell
    through silently (Path(...).relative_to(root) raises ValueError, not caught by anything else)
    and leaked raw container paths like "/workspace/public/app.js" straight into the chat UI.
    """
    if not path_str:
        return path_str
    if root:
        try:
            return str(Path(path_str).relative_to(root))
        except ValueError:
            pass
    try:
        return str(PurePosixPath(path_str).relative_to(_ISOLATED_MOUNT_ROOT))
    except ValueError:
        return path_str


def _map_event(
    payload: dict[str, Any],
    *,
    workspace_root: Path | None = None,
) -> list[TextDelta | ToolCallRequested | ToolCallResult]:
    """Translation from Codex CLI's `--json` event stream into our internal event types.

    Confirmed against a real `codex exec --json` run (codex-cli 0.144.5) - not a guess. Shape:
    top-level events are flat ({"type": "turn.started"}, {"type": "turn.completed", "usage": {}},
    {"type": "turn.failed", "error": {"message": ...}}), and per-item activity comes as
    {"type": "item.started" | "item.completed", "item": {"id", "type", ...}} pairs, where
    item.type is "agent_message" (text, delivered whole - no token-level deltas over this
    interface), "command_execution" (shell), or "file_change" (patch). turn.completed/
    turn.failed are handled by _handle_terminal below, not here.

    This is the one place to update if a Codex CLI upgrade changes event shape/names -
    unrecognized event/item types are silently dropped rather than treated as fatal."""
    kind = payload.get("type")
    if kind not in ("item.started", "item.completed"):
        return []

    item = payload.get("item")
    if not isinstance(item, dict):
        return []
    item_type = item.get("type")
    call_id = str(item.get("id") or uuid.uuid4().hex)

    if item_type == "agent_message":
        if kind != "item.completed":
            return []
        text = item.get("text") or ""
        return [TextDelta(text=text)] if text else []

    if item_type == "command_execution":
        if kind == "item.started":
            return [
                ToolCallRequested(
                    call_id=call_id,
                    name="command_execution",
                    arguments={"command": item.get("command") or ""},
                )
            ]
        exit_code = item.get("exit_code")
        output = str(item.get("aggregated_output") or "")[-4000:]
        ok = exit_code == 0
        # A bare exit code means nothing to the non-technical users this product targets - the
        # full log is still in `content` below for anyone who wants it, but the headline text
        # shouldn't be raw shell status. On failure, the last non-empty output line usually *is*
        # the actual error (e.g. "bash: eslint: command not found"), so surface it inline instead
        # of making the user open a separate log to find out.
        if ok:
            summary = "Готово"
        else:
            last_line = next((ln for ln in reversed(output.strip().splitlines()) if ln.strip()), "")
            summary = f"Ошибка: {last_line.strip()[:200]}" if last_line else "Команда завершилась с ошибкой"
        return [
            ToolCallResult(
                call_id=call_id,
                name="command_execution",
                ok=ok,
                summary=summary,
                content=output,
            )
        ]

    if item_type == "file_change":
        changes = item.get("changes")
        raw_paths = (
            [c.get("path", "") for c in changes if isinstance(c, dict)]
            if isinstance(changes, list)
            else []
        )
        names = ", ".join(_relativize(p, workspace_root) for p in raw_paths if p)
        if kind == "item.started":
            return [
                ToolCallRequested(call_id=call_id, name="file_change", arguments={"files": names})
            ]
        return [
            ToolCallResult(
                call_id=call_id,
                name="file_change",
                ok=True,
                summary=f"Изменено: {names}" if names else "Файлы изменены",
            )
        ]

    return []


def _with_paragraph_breaks(
    events: list[TextDelta | ToolCallRequested | ToolCallResult], seen_text: list[bool]
) -> list[TextDelta | ToolCallRequested | ToolCallResult]:
    """Codex delivers each agent_message item as one whole TextDelta, not token deltas (see
    _map_event's docstring). A turn that produces more than one - an early "here's my plan"
    message, then a later "adjusting because X" one - would otherwise get glued together with no
    separator once chat.py concatenates them into assistant_full (observed in the wild as
    sentences fused mid-word, e.g. "...сборку.В каталоге..."). Insert a paragraph break before
    every message after the first one seen in this run.
    """
    out: list[TextDelta | ToolCallRequested | ToolCallResult] = []
    for event in events:
        if isinstance(event, TextDelta) and event.text:
            if seen_text[0]:
                event = TextDelta(text="\n\n" + event.text)
            seen_text[0] = True
        out.append(event)
    return out


def _write_temp_images(root: Path, images: list[ImageAttachment]) -> list[str]:
    tmp_dir = root / ".airuntime" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for index, image in enumerate(images):
        ext = (image.content_type.split("/")[-1] or "png").split(";")[0] or "png"
        path = tmp_dir / f"upload_{uuid.uuid4().hex}_{index}.{ext}"
        path.write_bytes(base64.b64decode(image.data_base64))
        paths.append(str(path))
    return paths


def _cleanup_paths(paths: list[str]) -> None:
    for raw in paths:
        try:
            Path(raw).unlink(missing_ok=True)
        except OSError:
            pass


def _collect_requests(workspace: WorkspaceTools) -> None:
    """After a run, pick up any secret_/service_ request marker files Codex wrote (see
    _CODEX_BRIDGE_INSTRUCTIONS) and feed them into the same workspace.requested_* lists the old
    request_secret/request_service tools populated, so chat.py's existing handling of those
    lists (creating placeholder rows, provisioning services) needs no changes."""
    requests_dir = workspace.root / ".airuntime" / "requests"
    if not requests_dir.exists():
        return
    for path in sorted(requests_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            path.unlink(missing_ok=True)
            continue
        if not isinstance(data, dict):
            path.unlink(missing_ok=True)
            continue
        if path.name.startswith("secret__"):
            key = str(data.get("key") or "").strip()
            if key:
                workspace.requested_secrets.append((key, str(data.get("reason") or "").strip()))
        elif path.name.startswith("service__"):
            kind = str(data.get("kind") or "").strip()
            if kind:
                env = data.get("env")
                workspace.requested_services.append(
                    ServiceRequest(
                        kind=kind,
                        reason=str(data.get("reason") or "").strip(),
                        image=data.get("image") if isinstance(data.get("image"), str) else None,
                        env=env if isinstance(env, dict) else None,
                        data_path=data.get("data_path")
                        if isinstance(data.get("data_path"), str)
                        else None,
                    )
                )
        path.unlink(missing_ok=True)


def _compose_prompt(*, system_prompt: str, history: list[dict[str, str]], user_message: str) -> str:
    parts = [system_prompt.strip(), _CODEX_BRIDGE_INSTRUCTIONS]
    if history:
        transcript = "\n\n".join(f"{item['role']}: {item['content']}" for item in history)
        parts.append(f"--- Переписка в этом чате ранее ---\n{transcript}")
    parts.append(f"--- Новое сообщение пользователя ---\n{user_message}")
    return "\n\n".join(parts)


class CodexAgentSession:
    """Same public shape as agent.loop.CodingAgentSession (an async .run() yielding
    TextDelta/ToolCallRequested/ToolCallResult/AgentDone), backed by Codex CLI instead of a
    direct provider HTTP stream."""

    def __init__(self, *, model: str, workspace: WorkspaceTools | None, system_prompt: str) -> None:
        self.model = model
        self.workspace = workspace
        self.system_prompt = system_prompt

    def _handle_terminal(self, payload: dict[str, Any]) -> AgentDone | None:
        # Bare {"type": "error", "message": ...} events (straight from codex's own JSONL
        # stream) are non-fatal transient warnings - e.g. one reconnect attempt among several -
        # confirmed by observing them fire repeatedly while codex still recovered on its own.
        # Only turn.completed/turn.failed (from codex) or infra_error (synthesized by our own
        # code below/in codex_worker.py, always immediately followed by the generator ending -
        # a missing key, a dead container, a timeout) actually end the turn.
        kind = payload.get("type")
        if kind == "turn.completed":
            if self.workspace:
                _collect_requests(self.workspace)
            usage = payload.get("usage")
            return AgentDone(reason="stop", usage=usage if isinstance(usage, dict) else None)
        if kind == "turn.failed":
            error = payload.get("error")
            message = error.get("message") if isinstance(error, dict) else None
            return AgentDone(reason="error", error=message or "Codex turn failed")
        if kind == "infra_error":
            return AgentDone(reason="error", error=str(payload.get("message") or "Codex error"))
        return None

    async def run(
        self,
        *,
        history: list[dict[str, str]],
        user_message: str,
        images: list[ImageAttachment] | None = None,
    ) -> AsyncIterator[TextDelta | ToolCallRequested | ToolCallResult | AgentDone]:
        prompt = _compose_prompt(
            system_prompt=self.system_prompt, history=history, user_message=user_message
        )
        project_id = self.workspace.project_id if self.workspace else None
        cwd = f"{settings.generated_projects_dir}/{project_id}" if project_id else None

        image_paths: list[str] = []
        if images and self.workspace:
            image_paths = _write_temp_images(self.workspace.root, images)

        try:
            if in_worker_inline_docker():
                async for event in self._run_inline(
                    cwd=cwd, prompt=prompt, image_paths=image_paths
                ):
                    yield event
            else:
                async for event in self._run_via_queue(
                    project_id=project_id, cwd=cwd, prompt=prompt, image_paths=image_paths
                ):
                    yield event
        finally:
            _cleanup_paths(image_paths)

    async def _run_inline(
        self, *, cwd: str | None, prompt: str, image_paths: list[str]
    ) -> AsyncIterator[TextDelta | ToolCallRequested | ToolCallResult | AgentDone]:
        """Already running inside the worker process (a repair flow under
        worker_inline_docker()) - call agent/codex_worker.py directly instead of queueing, since
        the single worker process is the only thing that could ever service that queue."""
        from src.services.agent.codex_worker import iter_codex_events

        job = {
            "cwd": cwd,
            "model": self.model,
            "prompt": prompt,
            "image_paths": image_paths,
        }
        saw_event = False
        seen_text = [False]
        for payload in iter_codex_events(job):
            saw_event = True
            terminal = self._handle_terminal(payload)
            if terminal is not None:
                yield terminal
                return
            for event in _with_paragraph_breaks(
                _map_event(payload, workspace_root=self.workspace.root if self.workspace else None),
                seen_text,
            ):
                yield event

        if self.workspace:
            _collect_requests(self.workspace)
        yield AgentDone(
            reason="stop" if saw_event else "error",
            error=None if saw_event else "Codex did not respond",
        )

    async def _run_via_queue(
        self, *, project_id: str | None, cwd: str | None, prompt: str, image_paths: list[str]
    ) -> AsyncIterator[TextDelta | ToolCallRequested | ToolCallResult | AgentDone]:
        run_id = _submit_run(
            project_id=project_id,
            cwd=cwd,
            model=self.model,
            prompt=prompt,
            image_paths=image_paths,
            timeout_seconds=settings.codex_turn_timeout_seconds,
        )

        saw_event = False
        seen_text = [False]
        async for payload in _stream_events(
            run_id, timeout_seconds=settings.codex_turn_timeout_seconds
        ):
            saw_event = True
            terminal = self._handle_terminal(payload)
            if terminal is not None:
                yield terminal
                return
            for event in _with_paragraph_breaks(
                _map_event(payload, workspace_root=self.workspace.root if self.workspace else None),
                seen_text,
            ):
                yield event

        if self.workspace:
            _collect_requests(self.workspace)
        yield AgentDone(
            reason="stop" if saw_event else "error",
            error=None if saw_event else "Codex did not respond",
        )


async def codex_simple_complete(
    *,
    system_prompt: str,
    user_text: str,
    model: str,
    timeout_seconds: int | None = None,
) -> str:
    """One-shot text completion via Codex for the lightweight non-coding call sites (chat title/
    summary in chat_context.py, moderation classification in moderation.py) - no project
    workspace, no file/Docker access needed. Only ever called from the backend API process (see
    call sites), so this always takes the queued path - never in_worker_inline_docker(). Fails
    open (returns "") on any error or timeout, matching the previous HTTP-provider behavior at
    these call sites."""
    effective_timeout = timeout_seconds or settings.codex_simple_timeout_seconds
    try:
        run_id = _submit_run(
            project_id=None,
            cwd=None,
            model=model,
            prompt=f"{system_prompt.strip()}\n\n--- Текст ---\n{user_text}",
            image_paths=[],
            timeout_seconds=effective_timeout,
        )
    except Exception:  # noqa: BLE001 - Redis being down must never break chat/moderation
        return ""

    text_parts: list[str] = []
    try:
        async for payload in _stream_events(run_id, timeout_seconds=effective_timeout):
            kind = payload.get("type")
            if kind in ("turn.failed", "infra_error"):
                return ""
            if kind == "turn.completed":
                break
            for event in _map_event(payload):
                if isinstance(event, TextDelta):
                    text_parts.append(event.text)
    except Exception:  # noqa: BLE001
        return ""
    return "".join(text_parts).strip()
