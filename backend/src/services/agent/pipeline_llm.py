"""One-shot structured-output completion for the product pipeline's brief/review calls.

Deliberately NOT a tool-loop turn (no CodingAgentSession, no workspace tools) - these are
single text-in/JSON-out calls, "без истории рассуждений создающего агента" per the spec.
Reuses the two completion primitives that already exist for this exact shape of call:
codex_simple_complete (openai path, already used for chat title/summary + moderation) and
AgentProvider.stream_turn with no tools (anthropic/gemini/openrouter path, same adapters
loop.py already drives for the main turn). No new provider wire format needed.
"""

from __future__ import annotations

import json
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from src.services.agent.codex_runtime import CODEX_ELIGIBLE_PROVIDERS, codex_simple_complete
from src.services.agent.events import TextDelta, TurnFinished
from src.services.agent.providers import get_agent_provider
from src.services.file_context import ImageAttachment

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

_JSON_ONLY_SUFFIX = (
    "\n\nОтветь СТРОГО одним JSON-объектом по указанной схеме, без markdown-обрамления "
    "вроде ```, без текста до или после JSON."
)


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


async def _raw_complete(
    *,
    provider_name: str,
    model: str,
    api_key: str,
    system_prompt: str,
    user_text: str,
    timeout_seconds: int,
    images: list[ImageAttachment] | None = None,
) -> str:
    if provider_name in CODEX_ELIGIBLE_PROVIDERS:
        if images:
            # Codex CLI would need this project's actual workspace mounted to read image
            # files from disk (see codex_worker.py's cwd=None -> "nothing to mount" path) -
            # doing that would hand the review call the same file/shell access as the
            # creating agent, defeating the point of an independent reviewer. Text-only here
            # is a deliberate scope boundary, not an oversight - see this module's docstring.
            logger.info(
                "complete_structured: %d image(s) requested but the openai/Codex path is "
                "text-only for one-shot calls - continuing without them.",
                len(images),
            )
        return await codex_simple_complete(
            system_prompt=system_prompt,
            user_text=user_text,
            model=model,
            timeout_seconds=timeout_seconds,
        )

    provider = get_agent_provider(provider_name)
    text_parts: list[str] = []
    messages = provider.build_messages([], user_text, images=images or [])
    async for event in provider.stream_turn(
        system_prompt=system_prompt,
        messages=messages,
        tools=[],
        model=model,
        api_key=api_key,
    ):
        if isinstance(event, TextDelta):
            if event.text:
                text_parts.append(event.text)
        elif isinstance(event, TurnFinished):
            if event.stop_reason == "error":
                logger.warning("pipeline_llm one-shot call failed: %s", event.error)
                return ""
    return "".join(text_parts).strip()


def _parse(raw: str, response_model: type[ModelT]) -> tuple[ModelT | None, str | None]:
    """Returns (value, None) on success or (None, error_detail) otherwise - error_detail
    feeds the repair-retry prompt, so it stays a plain string rather than an exception."""
    if not raw:
        return None, "empty response"
    try:
        data = json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        return None, str(exc)
    try:
        return response_model.model_validate(data), None
    except ValidationError as exc:
        return None, str(exc)


async def complete_structured(
    *,
    provider_name: str,
    model: str,
    api_key: str,
    system_prompt: str,
    user_text: str,
    response_model: type[ModelT],
    timeout_seconds: int = 60,
    images: list[ImageAttachment] | None = None,
) -> ModelT | None:
    """Ask the model for one JSON object matching response_model. Never raises - on any
    failure (empty response, malformed JSON, schema mismatch) tries exactly one repair
    round-trip, then returns None so the caller can fail open (skip this pipeline stage)
    rather than block the turn.

    `images` (optional - e.g. review screenshots) are embedded via each provider's own
    build_messages(), so they land in whatever wire format that provider expects (Anthropic
    base64 image blocks, OpenAI-compatible data-URI image_url, Gemini inline_data). Ignored
    (not dropped silently - see _raw_complete) on the openai/Codex path."""
    prompt = system_prompt + _JSON_ONLY_SUFFIX
    raw = await _raw_complete(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        system_prompt=prompt,
        user_text=user_text,
        timeout_seconds=timeout_seconds,
        images=images,
    )
    value, error_detail = _parse(raw, response_model)
    if value is not None:
        return value

    logger.info(
        "pipeline_llm structured output needed a repair retry: %s", (error_detail or "")[:300]
    )
    repair_text = (
        f"{user_text}\n\n--- Твой предыдущий ответ не прошёл валидацию ---\n"
        f"{raw[:4000]}\n--- Ошибка ---\n{(error_detail or '')[:1000]}\n"
        "Верни ТОЛЬКО исправленный JSON-объект по требуемой схеме."
    )
    raw_retry = await _raw_complete(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        system_prompt=prompt,
        user_text=repair_text,
        timeout_seconds=timeout_seconds,
        images=images,
    )
    retry_value, retry_error = _parse(raw_retry, response_model)
    if retry_value is not None:
        return retry_value

    logger.warning(
        "pipeline_llm structured output failed after repair retry (provider=%s model=%s): %s",
        provider_name,
        model,
        (retry_error or "")[:300],
    )
    return None
