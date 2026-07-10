"""Lightweight safety classifier for user project requests.

Reuses the same per-provider streaming adapters as the coding agent (so it works with
whichever provider/key the platform already has configured), just with a dedicated
system prompt, no tools, and the output parsed as a small JSON verdict instead of shown
to the user.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from src.services.agent.events import TextDelta
from src.services.agent.providers import get_agent_provider

_MODERATION_SYSTEM_PROMPT = (
    "Ты - классификатор безопасности платформы, которая по запросу пользователя в чате "
    "генерирует код сайтов и Telegram-ботов. Тебе дают одно сообщение пользователя. Определи, "
    "не просит ли оно создать что-то из следующих категорий:\n"
    "- malware: вредоносное ПО, вирусы, трояны, кейлоггеры, шифровальщики-вымогатели, эксплойты\n"
    "- miner: скрытый/несогласованный крипто-майнинг чужих ресурсов\n"
    "- scam: мошенничество - фишинг, поддельные платёжные страницы, финансовые пирамиды, "
    "обман пользователей ради выгоды\n"
    "- terrorism: пропаганда терроризма, инструкции по насилию, вербовка\n"
    "- hate: нацистская/фашистская символика или идеология, разжигание ненависти по расе, "
    "национальности, религии\n"
    "- csam: сексуальный контент с несовершеннолетними\n\n"
    "Обычные легитимные сайты, лендинги, боты поддержки, магазины, игры, инструменты, даже "
    "спорные с точки зрения вкуса темы - НЕ блокируй, только явные нарушения из списка выше. "
    "Технический контекст (упоминание Docker, Telegram API, БД) сам по себе не повод для блокировки.\n\n"
    'Ответь СТРОГО одним JSON-объектом без markdown и пояснений: {"blocked": false} если всё в '
    'порядке, или {"blocked": true, "category": "<одна из категорий выше>", "reason": '
    '"<одно короткое предложение на русском, почему заблокировано>"} если нарушает.'
)


@dataclass(frozen=True)
class ModerationVerdict:
    blocked: bool
    category: str = ""
    reason: str = ""


async def check_project_safety(
    *, text: str, provider_name: str, model: str, api_key: str
) -> ModerationVerdict:
    """Fail-open: any error or unparsable response is treated as not-blocked, so a classifier
    hiccup never breaks the product for legitimate users - this is defense in depth, not the
    only safety layer."""
    if not text.strip() or not api_key:
        return ModerationVerdict(blocked=False)

    provider = get_agent_provider(provider_name)
    messages = provider.build_messages([], text[:4000])
    collected = ""
    try:
        async for event in provider.stream_turn(
            system_prompt=_MODERATION_SYSTEM_PROMPT,
            messages=messages,
            tools=[],
            model=model,
            api_key=api_key,
        ):
            if isinstance(event, TextDelta):
                collected += event.text
    except Exception:  # defensive: moderation must never take the whole turn down
        return ModerationVerdict(blocked=False)

    match = re.search(r"\{.*\}", collected, flags=re.DOTALL)
    if not match:
        return ModerationVerdict(blocked=False)
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return ModerationVerdict(blocked=False)

    if not isinstance(payload, dict) or not payload.get("blocked"):
        return ModerationVerdict(blocked=False)
    return ModerationVerdict(
        blocked=True,
        category=str(payload.get("category") or "other")[:64],
        reason=str(payload.get("reason") or "")[:500],
    )
