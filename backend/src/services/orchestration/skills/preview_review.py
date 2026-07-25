"""visual_preview_review / accessibility_review - generalizes product_pipeline.py's
preview+review loop into a reusable skill instead of code duplication: same network-isolated
headless-browser preview (preview_runner.py, reached only via the docker_control_queue RPC -
this module never touches Docker directly), same independent-reviewer-gets-no-code-access
contract, same deterministic pre-gate before spending an LLM call on an obviously-broken
preview.

accessibility_review is the same underlying flow with the review prompt narrowed to
accessibility-specific findings (contrast/semantics/aria) rather than full product quality -
still one preview run, just a different system prompt and which ReviewScore field the
completeness check leans on.
"""

from __future__ import annotations

from src.services.agent.pipeline_llm import complete_structured
from src.services.agent.pipeline_models import PreviewResult, ReviewResult
from src.services.docker_control_queue import submit_control_job
from src.services.orchestration.schemas import (
    RetryPolicy,
    RiskLevel,
    SkillDefinition,
    SkillResult,
    SpecialistRole,
)
from src.services.orchestration.skills.base import SkillContext
from src.services.orchestration.skills.common import BaseSkill

_REVIEW_SYSTEM_PROMPT = """Ты - независимый ревьюер качества продукта на платформе AIRuntime.
Тебе НЕ показывают код или рассуждения агента, который делал сайт - только бриф (цель и
критерии приёмки) и результат автоматической проверки в браузере (текст и заголовки страницы,
консольные ошибки, битые ссылки/картинки, переполнения). Оцени, стал ли запрос пользователя
реальным работающим продуктом."""

_ACCESSIBILITY_SYSTEM_PROMPT = """Ты - независимый ревьюер доступности (accessibility) на
платформе AIRuntime. Тебе НЕ показывают код - только результат автоматической проверки в
браузере. Сфокусируйся на: контрасте, семантической разметке, alt-тексте изображений,
доступности с клавиатуры, aria-атрибутах. Не оценивай общий дизайн вне доступности."""

_INFRA_FAILURE_MARKERS = (
    "worker may be unavailable",
    "is not built yet",
    "could not reach docker",
    "timed out after",
)


def _is_infra_failure(preview: PreviewResult) -> bool:
    if preview.status != "failed":
        return False
    return any(
        any(marker in err.lower() for marker in _INFRA_FAILURE_MARKERS)
        for err in preview.fatal_errors
    )


def _deterministic_gate(preview: PreviewResult) -> ReviewResult | None:
    if preview.status == "failed" or preview.fatal_errors:
        return ReviewResult(
            verdict="blocked", critical_issues=list(preview.fatal_errors) or ["preview failed"]
        )
    if any(page.broken_images for page in preview.pages):
        return ReviewResult(verdict="revise", major_issues=["broken images detected in preview"])
    return None


class _PreviewReviewSkillBase(BaseSkill):
    _system_prompt: str

    async def execute(self, context: SkillContext) -> SkillResult:
        targets = context.arguments.get("targets") or [
            {"path": "/", "viewport": {"width": 1440, "height": 900}}
        ]
        raw = await self._run_preview(context, targets)
        if raw is None:
            return SkillResult(
                status="failed", summary="preview RPC timed out or worker unreachable"
            )

        try:
            preview = PreviewResult.model_validate(raw)
        except Exception as exc:  # noqa: BLE001
            return SkillResult(
                status="failed", summary=f"preview result did not match expected shape: {exc}"
            )

        if _is_infra_failure(preview):
            return SkillResult(
                status="failed",
                summary="preview infrastructure unavailable (not a content problem)",
                output={"preview": preview.model_dump(), "infra_failure": True},
            )

        gated = _deterministic_gate(preview)
        brief_text = context.arguments.get("brief_text", "")
        user_text = f"Бриф (цель и критерии приёмки):\n{brief_text}\n\nРезультат автоматической проверки в браузере:\n{preview.model_dump_json(indent=2)}"

        review = await complete_structured(
            provider_name=context.arguments["provider_name"],
            model=context.arguments["model"],
            api_key=context.arguments["api_key"],
            system_prompt=self._system_prompt,
            user_text=user_text,
            response_model=ReviewResult,
            timeout_seconds=90,
        )
        if review is None:
            review = gated or ReviewResult(
                verdict="revise", major_issues=["review call failed - treating as needs-revision"]
            )
        elif gated is not None:
            # Deterministic findings are merged into, never overridden by, the LLM verdict -
            # same rule product_pipeline.py's own gate follows.
            review = review.model_copy(
                update={
                    "critical_issues": [*review.critical_issues, *gated.critical_issues],
                    "major_issues": [*review.major_issues, *gated.major_issues],
                    "verdict": "blocked" if gated.verdict == "blocked" else review.verdict,
                }
            )

        needs_fix = review.verdict in ("revise", "blocked") or bool(review.critical_issues)
        return SkillResult(
            status="partial" if needs_fix else "completed",
            summary=f"review verdict={review.verdict}",
            output={"preview": preview.model_dump(), "review": review.model_dump()},
        )

    async def _run_preview(self, context: SkillContext, targets: list[dict]) -> dict | None:
        import asyncio

        return await asyncio.to_thread(
            submit_control_job,
            action="preview",
            project_id=context.project_id,
            timeout_seconds=120,
            extra={"targets": targets},
        )


class VisualPreviewReviewSkill(_PreviewReviewSkillBase):
    _system_prompt = _REVIEW_SYSTEM_PROMPT
    definition = SkillDefinition(
        id="visual_preview_review",
        version="1.0",
        title="Visual preview review",
        description="Render the project in an isolated headless browser and have an independent reviewer assess it against the brief.",
        supported_roles=[SpecialistRole.QA_REVIEWER, SpecialistRole.UI_UX_SPECIALIST],
        supported_project_types=["website", "mixed"],
        input_schema={
            "targets": "list[{path,viewport}]",
            "brief_text": "string",
            "provider_name": "string",
            "model": "string",
            "api_key": "string",
        },
        output_schema={"preview": "object", "review": "object"},
        risk_level=RiskLevel.LOW,
        idempotent=True,
        retry_policy=RetryPolicy(max_attempts=2),
    )


class AccessibilityReviewSkill(_PreviewReviewSkillBase):
    _system_prompt = _ACCESSIBILITY_SYSTEM_PROMPT
    definition = SkillDefinition(
        id="accessibility_review",
        version="1.0",
        title="Accessibility review",
        description="Same isolated preview as visual_preview_review, reviewed specifically for accessibility issues.",
        supported_roles=[SpecialistRole.QA_REVIEWER, SpecialistRole.UI_UX_SPECIALIST],
        supported_project_types=["website", "mixed"],
        input_schema={
            "targets": "list[{path,viewport}]",
            "brief_text": "string",
            "provider_name": "string",
            "model": "string",
            "api_key": "string",
        },
        output_schema={"preview": "object", "review": "object"},
        risk_level=RiskLevel.LOW,
        idempotent=True,
        retry_policy=RetryPolicy(max_attempts=2),
    )
