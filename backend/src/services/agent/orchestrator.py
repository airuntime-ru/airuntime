"""Optional request-decomposition layer in front of the normal single-turn coding agent.

Off by default (settings.enable_agent_orchestrator) - this is the least-verified piece of the
2026-07-17 architecture work. Everything else that shipped alongside it (the exit-1 status bug,
the per-project Codex isolation, the metrics footer) was checked against static analysis, offline
migration SQL, or logic simulations; this module's actual decomposition quality can only really be
judged by running it against a live model on a real complex request, which wasn't available here.
Turn it on, try a genuinely multi-domain prompt ("сайт с личным кабинетом, админкой на отдельном
поддомене и telegram-ботом уведомлений"), and read the "Часть N/M" narration it produces before
trusting it broadly.

Only changes behavior for the Codex-eligible path (CODEX_ELIGIBLE_PROVIDERS) - callers on other
providers, or with the flag off, go straight to the normal CodingAgentSession.run() they always
used; this module is an alternative *producer* of the exact same TextDelta/ToolCallRequested/
ToolCallResult/AgentDone event stream, not a replacement for how chat.py consumes it.

Design choices, and why:
- A cheap planning call (via codex_runtime.codex_simple_complete) decides whether to decompose at
  all, and defaults to "don't" on any doubt, error, short message, or malformed response - most
  turns (one bug fix, one small feature in an existing project) are not worth the extra
  planning-call latency/cost and should just run normally. See _plan_subtasks.
- Sequential, not parallel, subtask execution. Every subtask shares the SAME project workspace
  (they're all editing the same one project, just focused on different concerns) - two
  independent Codex containers writing into that workspace at once would race each other. Codex's
  own native subagents (see codex_runtime.py's bridge instructions, added the same day) already
  give real parallelism *within* one Codex process/container, which can coordinate its own file
  access; this module intentionally does not try to out-parallelize that at the platform level
  without per-subtask workspace isolation first - a natural follow-up once per-project isolation
  (codex_worker.py) extends to per-subtask, not done here.
- One subtask failing doesn't abort the rest - partial progress across the parts that did work
  beats losing everything because one part hit a snag, the same "degrade, don't hard-fail"
  philosophy as codex_worker.py's mount-resolution fallback.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

from src.core.config import settings
from src.services.agent.codex_runtime import CODEX_ELIGIBLE_PROVIDERS, codex_simple_complete
from src.services.agent.events import AgentDone, TextDelta, ToolCallRequested, ToolCallResult
from src.services.agent.loop import CodingAgentSession
from src.services.agent.tools import WorkspaceTools
from src.services.file_context import ImageAttachment

_MAX_SUBTASKS = 4
# Below this, a request is almost never a multi-domain build worth an extra planning call and
# sequential sub-runs - "поправь цвет кнопки" shouldn't pay that latency to be told "no".
_MIN_MESSAGE_CHARS_FOR_PLANNING = 120

_PLANNING_PROMPT = """\
Ты - архитектор, который решает, стоит ли разбить входящий запрос пользователя на независимые \
крупные части и поручить каждую отдельному проходу кодящего агента.

Дели ТОЛЬКО если запрос реально распадается на крупные куски, не зависящие друг от друга по \
результату (например: инфраструктура/окружение отдельно от бизнес-логики бэкенда отдельно от \
фронтенда/дизайна), и это по-настоящему объёмный запрос. Для обычной задачи (один сайт, один \
бот, один баг-фикс, доработка существующего проекта, любое уточнение) НЕ дели - в подавляющем \
большинстве случаев правильный ответ - не делить вообще.

Ответь СТРОГО одним JSON-объектом, без markdown-обрамления вроде ```, в одном из двух видов:
{"subtasks": []}
или
{"subtasks": [{"title": "...", "instructions": "..."}, {"title": "...", "instructions": "..."}]}

Не больше 4 частей. "title" - 2-4 слова для интерфейса (например "Инфраструктура и сервисы"). \
"instructions" - конкретное самодостаточное задание для этой части: пиши так, будто инструктируешь \
отдельного человека, который не видел это рассуждение и не увидит остальные части - только свой \
instructions и историю чата.

Запрос пользователя:
"""


@dataclass
class Subtask:
    title: str
    instructions: str


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    text = text[3:]
    if "\n" in text:
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


async def _plan_subtasks(*, model: str, user_message: str) -> list[Subtask]:
    """Never raises - any failure (timeout, malformed JSON, wrong shape) means "don't decompose",
    the same fail-open posture codex_simple_complete itself already has."""
    if len(user_message) < _MIN_MESSAGE_CHARS_FOR_PLANNING:
        return []
    try:
        raw = await codex_simple_complete(
            system_prompt=_PLANNING_PROMPT,
            user_text=user_message,
            model=model,
            timeout_seconds=settings.codex_simple_timeout_seconds,
        )
        if not raw:
            return []
        data = json.loads(_strip_code_fence(raw))
        items = data.get("subtasks") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        subtasks: list[Subtask] = []
        for item in items[:_MAX_SUBTASKS]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            instructions = str(item.get("instructions") or "").strip()
            if title and instructions:
                subtasks.append(Subtask(title=title, instructions=instructions))
        # A single "subtask" is just the original request with extra steps - only worth the
        # multi-pass overhead once there are genuinely multiple independent pieces.
        return subtasks if len(subtasks) >= 2 else []
    except (json.JSONDecodeError, AttributeError, TypeError, KeyError):
        return []


def _compose_subtask_prompt(*, base_system_prompt: str, subtask: Subtask, total: int) -> str:
    return (
        f"{base_system_prompt}\n\n"
        "ВАЖНО про эту сессию: архитектор разбил исходный запрос пользователя на "
        f"{total} независимые части, и сейчас ты выполняешь ровно одну - «{subtask.title}». "
        "Сосредоточься только на ней; остальные части выполняют отдельные проходы (до или после "
        "этого). Файлы проекта могут уже содержать результат других частей - начни как обычно с "
        "list_files/изучения текущего состояния, а не с чистого листа."
    )


async def run_agent_turn(
    *,
    provider_name: str,
    model: str,
    api_key: str,
    workspace: WorkspaceTools,
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
    images: list[ImageAttachment] | None = None,
) -> AsyncIterator[TextDelta | ToolCallRequested | ToolCallResult | AgentDone]:
    """Drop-in replacement for `CodingAgentSession(...).run(...)` that may, when enabled and
    worthwhile, run the turn as a sequence of focused sub-passes instead of one. Always yields the
    same event types a plain session.run() would, ending in exactly one AgentDone."""

    def _plain_session() -> CodingAgentSession:
        return CodingAgentSession(
            provider_name=provider_name,
            model=model,
            api_key=api_key,
            workspace=workspace,
            system_prompt=system_prompt,
        )

    if not settings.enable_agent_orchestrator or provider_name not in CODEX_ELIGIBLE_PROVIDERS:
        async for event in _plain_session().run(
            history=history, user_message=user_message, images=images
        ):
            yield event
        return

    subtasks = await _plan_subtasks(model=model, user_message=user_message)
    if not subtasks:
        async for event in _plain_session().run(
            history=history, user_message=user_message, images=images
        ):
            yield event
        return

    yield TextDelta(
        text=(
            f"Разбиваю задачу на {len(subtasks)} части: "
            + ", ".join(s.title for s in subtasks)
            + ".\n"
        )
    )

    had_success = False
    last_error: str | None = None
    usage_by_subtask: list[dict[str, object]] = []

    for index, subtask in enumerate(subtasks, start=1):
        yield TextDelta(text=f"\n\n**Часть {index}/{len(subtasks)} - {subtask.title}**\n")
        sub_prompt = _compose_subtask_prompt(
            base_system_prompt=system_prompt, subtask=subtask, total=len(subtasks)
        )
        sub_session = CodingAgentSession(
            provider_name=provider_name,
            model=model,
            api_key=api_key,
            workspace=workspace,
            system_prompt=sub_prompt,
        )
        async for event in sub_session.run(
            history=history, user_message=subtask.instructions, images=images
        ):
            if isinstance(event, AgentDone):
                if event.reason == "error":
                    last_error = event.error
                    yield TextDelta(text=f"\n_Эта часть завершилась с ошибкой: {event.error}_\n")
                else:
                    had_success = True
                if event.usage:
                    usage_by_subtask.append({"title": subtask.title, **event.usage})
            else:
                yield event

    if had_success:
        yield AgentDone(
            reason="stop",
            usage={"subtasks": usage_by_subtask} if usage_by_subtask else None,
        )
    else:
        yield AgentDone(
            reason="error",
            error=last_error or "Все части задачи завершились с ошибкой",
        )
