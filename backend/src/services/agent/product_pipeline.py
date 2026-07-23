"""Product-quality pipeline: brief -> UX -> visual direction -> implementation -> build ->
preview (multi-page, desktop+mobile) -> review (text + screenshots, per-provider) -> fix.

Off by default at the Settings class level (settings.enable_product_pipeline) - docker-compose
turns it on for actual deployments, see config.py's own comment. chat.py's _stream_events picks
this over plain orchestrator.run_agent_turn only when the flag is on; off, behavior is
byte-identical to before this module existed - the same "opt-in alternate producer of the same
event stream" shape orchestrator.py itself already uses for enable_agent_orchestrator.

Security invariants (do not weaken):
- No Docker socket on the backend process - preview goes through docker_control_queue's
  Redis RPC exactly like build_project already does (see agent/tools.py::_preview_project).
- No arbitrary shell/exec tool added anywhere in this pipeline.
- Secrets never enter planning artifacts, review prompts, or logged metrics.
- Screenshots stay as on-disk refs under .airuntime/preview/*; review images are read directly
  off disk and embedded via each provider's own build_messages() - never proxied through an
  extra shell/tool call. The openai/Codex path deliberately does NOT get review images (see
  _raw_complete's docstring) - giving Codex a real project mount just to read a screenshot
  would hand the "independent" reviewer the same file/shell access as the creating agent,
  which defeats the point of a separate review call.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.db.models.project import Project
from src.services.agent.events import AgentDone, TextDelta, ToolCallRequested, ToolCallResult
from src.services.agent.orchestrator import run_agent_turn
from src.services.agent.pipeline_llm import complete_structured
from src.services.agent.pipeline_models import (
    BriefOutcome,
    PreviewResult,
    ProductBrief,
    ReviewResult,
    UXSpec,
    VisualDirection,
)
from src.services.agent.pipeline_prompts import (
    BRIEF_SYSTEM_PROMPT,
    REVIEW_SYSTEM_PROMPT,
    UX_SYSTEM_PROMPT,
    VISUAL_SYSTEM_PROMPT,
    compose_brief_user_text,
    compose_fix_user_message,
    compose_review_user_text,
    compose_ux_user_text,
    compose_visual_user_text,
)
from src.services.agent.planning_store import (
    compose_planning_context,
    save_brief,
    save_preview,
    save_review,
    save_ux,
    save_visual,
)
from src.services.agent.tools import WorkspaceTools
from src.services.docker_control_queue import submit_control_job
from src.services.file_context import ImageAttachment
from src.services.system_settings import resolve_api_key_for_provider

logger = logging.getLogger(__name__)

# A review with no critical_issues but a very low score on any single dimension still forces
# a fix pass - "technically nothing flagged as critical" should not be enough on its own.
_LOW_SCORE_THRESHOLD = 55

_DESKTOP_VIEWPORT = {"width": 1440, "height": 900}
_MOBILE_VIEWPORT = {"width": 390, "height": 844}
_MOBILE_WIDTH_THRESHOLD = 768

_MAX_REVIEW_IMAGES = 2
_MAX_REVIEW_IMAGE_BYTES = 4 * 1024 * 1024

# Independent of max_review_iterations - infra hiccups (worker down, image not built, a
# timeout) must not eat into the budget of content-fix passes the coding agent gets.
_MAX_INFRA_RETRIES = 1

# Heuristic filename guesses matching prompt.py's own _WEBSITE_RULES convention
# (login.html/cabinet.html/booking.html/history.html are literally named there), used only to
# pick a *few* extra pages worth checking - a wrong guess just shows up as a 404 in that one
# page's network_errors, it doesn't fail the whole preview.
_PATH_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("login", "вход", "авториз"), "/login.html"),
    (("cabinet", "кабинет", "личный кабинет"), "/cabinet.html"),
    (("booking", "запис", "бронир"), "/booking.html"),
    (("history", "истори"), "/history.html"),
    (("pricing", "прайс", "цен", "тариф"), "/pricing.html"),
    (("service", "услуг"), "/services.html"),
    (("contact", "контакт"), "/contacts.html"),
    (("faq",), "/faq.html"),
]

# Substrings that mean "the platform's own plumbing didn't work" (worker/Docker/RPC), as
# opposed to "the app loaded but is broken" - see _preview_infra_failure.
_INFRA_FAILURE_MARKERS = (
    "worker may be unavailable",
    "Preview control action failed",
    "is not built yet",
    "Could not reach Docker",
    "Docker error during preview",
    "timed out after",
    "Could not resolve project workspace path",
    "exited without producing a result",
    "Could not read preview result",
    "Invalid preview payload",
    "No project context for preview",
)


def _review_needs_fix(review: ReviewResult) -> bool:
    if review.verdict in ("revise", "blocked"):
        return True
    if review.critical_issues:
        return True
    return any(value < _LOW_SCORE_THRESHOLD for value in review.score.model_dump().values())


def _deterministic_review_gate(preview: PreviewResult) -> ReviewResult | None:
    """Hard blockers that do not need an LLM call - a fatal load failure (app is up but
    broken - infra-only failures are filtered out before this is ever called, see
    _preview_infra_failure) or a broken image must never pass as "ship it" even if the
    reviewer model call itself fails or is skipped. Returns None when preview found nothing a
    deterministic check can flag."""
    if preview.status == "failed" or preview.fatal_errors:
        return ReviewResult(
            verdict="blocked",
            critical_issues=list(preview.fatal_errors) or ["Проект не открылся в браузере"],
            recommended_fixes=["Почини причину сбоя и снова вызови build_project."],
        )
    broken = [img for page in preview.pages for img in page.broken_images]
    if broken:
        return ReviewResult(
            verdict="revise",
            critical_issues=[f"Битое изображение: {item}" for item in broken[:10]],
            recommended_fixes=[
                "Замени битые изображения на рабочие, типографику или предметный "
                "графический элемент."
            ],
        )
    return None


def _preview_infra_failure(preview: PreviewResult) -> str | None:
    """None unless preview failed for a platform-plumbing reason (worker unreachable, image
    not built, Docker error, timeout, ...) rather than the app itself being broken. Editing
    project code cannot fix any of these - they get a small, separately-budgeted retry
    instead of spending a normal fix-pass iteration on them."""
    if preview.status != "failed":
        return None
    for err in preview.fatal_errors:
        if any(marker in err for marker in _INFRA_FAILURE_MARKERS):
            return err
    return None


def _resolve_reviewer(provider_name: str, model: str, api_key: str) -> tuple[str, str, str]:
    """settings.reviewer_provider/reviewer_model let an admin pin review to a different
    provider/model than generation. The turn's own api_key only works for the turn's own
    provider - a pinned different provider needs ITS OWN configured key, not a reused,
    mismatched one (a bug in an earlier draft of this module silently reused the wrong key
    here, which fails auth 100% of the time it triggers - caught and fixed before shipping)."""
    review_provider = settings.reviewer_provider or provider_name
    review_model = settings.reviewer_model or model
    if review_provider == provider_name:
        return review_provider, review_model, api_key
    resolved = resolve_api_key_for_provider(review_provider) or getattr(
        settings, f"{review_provider}_api_key", None
    )
    if not resolved:
        logger.warning(
            "reviewer_provider=%s has no configured API key - falling back to the turn's own "
            "provider (%s) for review",
            review_provider,
            provider_name,
        )
        return provider_name, model, api_key
    return review_provider, review_model, resolved


def _supports_preview(project: Project) -> bool:
    return project.type in ("website", "mixed")


def _preview_paths_from_brief(brief: ProductBrief | None) -> list[str]:
    paths = ["/"]
    if brief is None:
        return paths
    haystack = [*brief.required_pages_or_flows, *brief.required_features]
    for item in haystack:
        lowered = item.lower()
        for keywords, path in _PATH_HINTS:
            if path not in paths and any(keyword in lowered for keyword in keywords):
                paths.append(path)
    return paths[:4]


def _preview_targets_from_brief(brief: ProductBrief | None) -> list[dict]:
    """Desktop checks for up to 4 pages guessed from the brief (always including the
    homepage), plus one mobile check of the homepage - bounded so a richer brief doesn't blow
    the preview container's time budget (see _run_preview's timeout scaling)."""
    paths = _preview_paths_from_brief(brief)
    targets = [{"path": path, "viewport": dict(_DESKTOP_VIEWPORT)} for path in paths]
    targets.append({"path": paths[0], "viewport": dict(_MOBILE_VIEWPORT)})
    return targets


async def _run_preview(workspace: WorkspaceTools, targets: list[dict]) -> PreviewResult:
    """Backend-safe: Redis RPC to the worker via the same submit_control_job primitive
    agent/tools.py's preview_project tool handler uses - never imports docker directly, and
    never receives a URL from the model (only same-origin relative paths, resolved server-side
    into `targets` before this call)."""
    if not workspace.project_id:
        return PreviewResult(status="failed", fatal_errors=["No project context for preview"])
    # Base budget covers one target; each additional one gets its own share of navigation/
    # scroll/screenshot time on top of the RPC's own generous slack.
    timeout = max(30, int(settings.preview_timeout_seconds) + 30 + 20 * max(0, len(targets) - 1))
    raw = await asyncio.to_thread(
        submit_control_job,
        action="preview",
        project_id=workspace.project_id,
        timeout_seconds=timeout,
        extra={"targets": targets},
    )
    if raw is None:
        return PreviewResult(
            status="failed",
            fatal_errors=["Preview service did not respond - worker may be unavailable"],
        )
    if "status" not in raw:
        # docker_control_actions.py's generic failure envelope ({"ok": False, "error": ...}).
        return PreviewResult(
            status="failed",
            fatal_errors=[str(raw.get("error") or "Preview control action failed")],
        )
    try:
        return PreviewResult.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - never break the turn on a malformed payload
        logger.warning("Preview result failed validation: %s", exc)
        return PreviewResult(status="failed", fatal_errors=[f"Invalid preview payload: {exc}"])


def _load_screenshot(workspace_root: Path, screenshot_ref: str) -> ImageAttachment | None:
    resolved_root = workspace_root.resolve()
    path = (workspace_root / screenshot_ref).resolve()
    if not path.is_relative_to(resolved_root):
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data or len(data) > _MAX_REVIEW_IMAGE_BYTES:
        if len(data) > _MAX_REVIEW_IMAGE_BYTES:
            logger.info(
                "Skipping oversized review screenshot %s (%d bytes)", screenshot_ref, len(data)
            )
        return None
    return ImageAttachment(
        filename=path.name,
        content_type="image/png",
        data_base64=base64.b64encode(data).decode("ascii"),
    )


def _select_review_screenshots(
    preview: PreviewResult, workspace_root: Path
) -> list[ImageAttachment]:
    """Up to one desktop + one mobile screenshot - real visual signal for the reviewer without
    an unbounded request payload. Never raises: a missing/oversized file is just skipped."""
    desktop_page = next(
        (
            p
            for p in preview.pages
            if p.screenshot_ref and p.viewport.width >= _MOBILE_WIDTH_THRESHOLD
        ),
        None,
    )
    mobile_page = next(
        (
            p
            for p in preview.pages
            if p.screenshot_ref and p.viewport.width < _MOBILE_WIDTH_THRESHOLD
        ),
        None,
    )
    images: list[ImageAttachment] = []
    for page in (desktop_page, mobile_page):
        if page is None or len(images) >= _MAX_REVIEW_IMAGES:
            continue
        image = _load_screenshot(workspace_root, page.screenshot_ref)
        if image is not None:
            images.append(image)
    return images


async def _plan_ux(
    *, provider_name: str, model: str, api_key: str, brief: ProductBrief, user_message: str
) -> UXSpec | None:
    return await complete_structured(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        system_prompt=UX_SYSTEM_PROMPT,
        user_text=compose_ux_user_text(brief=brief, user_message=user_message),
        response_model=UXSpec,
        timeout_seconds=60,
    )


async def _plan_visual(
    *,
    provider_name: str,
    model: str,
    api_key: str,
    brief: ProductBrief,
    ux: UXSpec | None,
    user_message: str,
) -> VisualDirection | None:
    return await complete_structured(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        system_prompt=VISUAL_SYSTEM_PROMPT,
        user_text=compose_visual_user_text(brief=brief, ux=ux, user_message=user_message),
        response_model=VisualDirection,
        timeout_seconds=60,
    )


async def run_product_pipeline(
    *,
    project: Project,
    provider_name: str,
    model: str,
    api_key: str,
    workspace: WorkspaceTools,
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
    images: list[ImageAttachment] | None = None,
) -> AsyncIterator[TextDelta | ToolCallRequested | ToolCallResult | AgentDone]:
    """Drop-in alternative to orchestrator.run_agent_turn - same event stream shape, ending in
    exactly one AgentDone. Only ever called when settings.enable_product_pipeline is True
    (chat.py branches to plain run_agent_turn otherwise, before this module is imported-used)."""
    metrics: dict[str, Any] = {
        "stages_s": {},
        "build_iterations": 0,
        "review_iterations": 0,
        "preview_failures": 0,
        "infra_retries": 0,
        "review_scores": [],
        "skipped_reason": None,
    }

    def _mark(stage: str, started: float) -> None:
        metrics["stages_s"][stage] = round(time.monotonic() - started, 3)

    def _finish_usage(turn_usage: dict[str, Any] | None) -> dict[str, Any]:
        merged = dict(turn_usage or {})
        merged["pipeline"] = metrics
        return merged

    try:
        # --- Brief -----------------------------------------------------------------
        brief: ProductBrief | None = None
        started = time.monotonic()
        yield ToolCallRequested(call_id="brief", name="product_brief", arguments={})
        outcome = await complete_structured(
            provider_name=provider_name,
            model=model,
            api_key=api_key,
            system_prompt=BRIEF_SYSTEM_PROMPT,
            user_text=compose_brief_user_text(
                project_name=project.name,
                project_description=project.description or "",
                project_type=project.type,
                user_message=user_message,
            ),
            response_model=BriefOutcome,
            timeout_seconds=60,
        )
        _mark("brief", started)

        if outcome is not None and outcome.clarifying_questions and outcome.brief is None:
            yield ToolCallResult(
                call_id="brief", name="product_brief", ok=True, summary="Нужны уточнения"
            )
            questions = outcome.clarifying_questions[:3]
            text = "Чтобы сделать продукт точно под задачу, уточните пару моментов:\n" + "\n".join(
                f"{i}. {q}" for i, q in enumerate(questions, start=1)
            )
            yield TextDelta(text=text)
            metrics["skipped_reason"] = "clarifying_questions"
            logger.info("pipeline_run_metrics %s", metrics)
            yield AgentDone(reason="stop", usage={"pipeline": metrics})
            return

        if outcome is not None and outcome.brief is not None:
            brief = outcome.brief
            save_brief(workspace.root, brief)
            yield ToolCallResult(
                call_id="brief", name="product_brief", ok=True, summary="Бриф продукта готов"
            )
        else:
            yield ToolCallResult(
                call_id="brief",
                name="product_brief",
                ok=False,
                summary="Не удалось сформировать бриф - продолжаю без него",
            )

        # --- UX + Visual direction ---------------------------------------------------
        ux: UXSpec | None = None
        visual: VisualDirection | None = None
        if brief is not None and settings.enable_ux_planning:
            started = time.monotonic()
            yield ToolCallRequested(call_id="ux", name="ux_planning", arguments={})
            ux = await _plan_ux(
                provider_name=provider_name,
                model=model,
                api_key=api_key,
                brief=brief,
                user_message=user_message,
            )
            _mark("ux", started)
            if ux is not None:
                save_ux(workspace.root, ux)
                yield ToolCallResult(
                    call_id="ux", name="ux_planning", ok=True, summary="UX-спецификация готова"
                )
            else:
                yield ToolCallResult(
                    call_id="ux",
                    name="ux_planning",
                    ok=False,
                    summary="UX-спека недоступна - пропускаю",
                )

        if brief is not None and settings.enable_visual_planning:
            started = time.monotonic()
            yield ToolCallRequested(call_id="visual", name="visual_direction", arguments={})
            visual = await _plan_visual(
                provider_name=provider_name,
                model=model,
                api_key=api_key,
                brief=brief,
                ux=ux,
                user_message=user_message,
            )
            _mark("visual", started)
            if visual is not None:
                save_visual(workspace.root, visual)
                yield ToolCallResult(
                    call_id="visual",
                    name="visual_direction",
                    ok=True,
                    summary=f"Визуальное направление: {visual.concept_name or 'готово'}",
                )
            else:
                yield ToolCallResult(
                    call_id="visual",
                    name="visual_direction",
                    ok=False,
                    summary="Визуальное направление недоступно - пропускаю",
                )

        enriched_prompt = system_prompt
        if brief is not None:
            planning_block = compose_planning_context(brief=brief, ux=ux, visual=visual)
            if planning_block:
                enriched_prompt = f"{system_prompt}\n\n{planning_block}"

        # --- Implement ---------------------------------------------------------------
        started = time.monotonic()
        turn_error: str | None = None
        turn_usage: dict[str, Any] | None = None
        async for event in run_agent_turn(
            provider_name=provider_name,
            model=model,
            api_key=api_key,
            workspace=workspace,
            system_prompt=enriched_prompt,
            history=history,
            user_message=user_message,
            images=images,
        ):
            if isinstance(event, AgentDone):
                turn_usage = event.usage
                if event.reason == "error":
                    turn_error = event.error
            else:
                if isinstance(event, ToolCallResult) and event.name == "build_project":
                    metrics["build_iterations"] += 1
                yield event
        _mark("implement", started)

        if turn_error:
            metrics["skipped_reason"] = "implementation_error"
            logger.info("pipeline_run_metrics %s", metrics)
            yield AgentDone(reason="error", error=turn_error, usage=_finish_usage(turn_usage))
            return

        # --- Preview + review + fix loop ----------------------------------------------
        max_iterations = max(0, int(settings.max_review_iterations))
        iteration = 0
        infra_retries = 0

        while (
            settings.enable_browser_preview
            and _supports_preview(project)
            and workspace.build_succeeded is not False
        ):
            started = time.monotonic()
            targets = _preview_targets_from_brief(brief)
            yield ToolCallRequested(
                call_id=f"preview-{iteration}",
                name="preview_project",
                arguments={"targets": targets},
            )
            preview = await _run_preview(workspace, targets)
            save_preview(workspace.root, preview)
            _mark(f"preview_{iteration}", started)
            preview_ok = preview.status != "failed"
            yield ToolCallResult(
                call_id=f"preview-{iteration}",
                name="preview_project",
                ok=preview_ok,
                summary=(
                    f"Preview {preview.status} ({len(preview.pages)}/{len(targets)} checked)"
                    if preview_ok
                    else f"Preview failed: {'; '.join(preview.fatal_errors)[:160]}"
                ),
                content=preview.model_dump_json(),
            )
            if not preview_ok:
                metrics["preview_failures"] += 1

            infra_error = _preview_infra_failure(preview)
            if infra_error is not None:
                if infra_retries >= _MAX_INFRA_RETRIES:
                    yield TextDelta(
                        text=(
                            "\n\nПроверка в браузере не смогла запуститься "
                            f"({infra_error}). Публикую как есть, без автоматического ревью.\n"
                        )
                    )
                    metrics["skipped_reason"] = "preview_infra_failure"
                    break
                infra_retries += 1
                metrics["infra_retries"] = infra_retries
                yield TextDelta(
                    text="\n\nПроверка в браузере не ответила — пересобираю и пробую ещё раз.\n"
                )
                await asyncio.to_thread(
                    submit_control_job,
                    action="build_check",
                    project_id=workspace.project_id,
                    timeout_seconds=180,
                )
                continue  # skip review this round - retry preview, not a content fix pass

            if not settings.enable_design_review:
                break

            started = time.monotonic()
            yield ToolCallRequested(
                call_id=f"review-{iteration}", name="design_review", arguments={}
            )
            gate = _deterministic_review_gate(preview)
            if gate is not None and gate.verdict == "blocked":
                review: ReviewResult | None = gate
            else:
                review_provider, review_model, review_api_key = _resolve_reviewer(
                    provider_name, model, api_key
                )
                review_images = _select_review_screenshots(preview, workspace.root)
                llm_review = await complete_structured(
                    provider_name=review_provider,
                    model=review_model,
                    api_key=review_api_key,
                    system_prompt=REVIEW_SYSTEM_PROMPT,
                    user_text=compose_review_user_text(brief=brief, preview=preview),
                    response_model=ReviewResult,
                    timeout_seconds=90,
                    images=review_images or None,
                )
                if llm_review is None:
                    review = gate  # may be None too - handled just below
                elif gate is not None:
                    # Merge deterministic findings (e.g. broken images) into the LLM verdict
                    # rather than letting the LLM silently overrule them.
                    merged = list(
                        dict.fromkeys([*gate.critical_issues, *llm_review.critical_issues])
                    )
                    llm_review.critical_issues = merged
                    if merged and llm_review.verdict == "pass":
                        llm_review.verdict = "revise"
                    review = llm_review
                else:
                    review = llm_review
            _mark(f"review_{iteration}", started)

            if review is None:
                yield ToolCallResult(
                    call_id=f"review-{iteration}",
                    name="design_review",
                    ok=False,
                    summary="Ревью недоступно - публикую как есть",
                )
                break

            save_review(workspace.root, review)
            metrics["review_iterations"] += 1
            metrics["review_scores"].append(review.score.model_dump())
            needs_fix = _review_needs_fix(review)
            yield ToolCallResult(
                call_id=f"review-{iteration}",
                name="design_review",
                ok=not needs_fix,
                summary=(
                    f"Ревью: {review.verdict}"
                    + (
                        f", критично: {len(review.critical_issues)}"
                        if review.critical_issues
                        else ""
                    )
                ),
                content=review.model_dump_json(),
            )

            if not needs_fix:
                break
            if iteration >= max_iterations:
                remaining = "; ".join((review.critical_issues + review.major_issues)[:3])
                yield TextDelta(
                    text=(
                        "\n\nАвтоматическая проверка нашла проблемы, но лимит попыток "
                        f"исправления исчерпан. Осталось: {remaining}\n"
                    )
                )
                break

            iteration += 1
            yield TextDelta(text="\n\nНашёл проблемы после проверки — исправляю.\n")
            fix_message = compose_fix_user_message(review=review)
            started = time.monotonic()
            fix_error: str | None = None
            async for event in run_agent_turn(
                provider_name=provider_name,
                model=model,
                api_key=api_key,
                workspace=workspace,
                system_prompt=enriched_prompt,
                history=history,
                user_message=fix_message,
                images=None,
            ):
                if isinstance(event, AgentDone):
                    if event.usage:
                        turn_usage = event.usage
                    if event.reason == "error":
                        fix_error = event.error
                else:
                    if isinstance(event, ToolCallResult) and event.name == "build_project":
                        metrics["build_iterations"] += 1
                    yield event
            _mark(f"fix_{iteration}", started)
            if fix_error:
                metrics["skipped_reason"] = "fix_pass_error"
                logger.info("pipeline_run_metrics %s", metrics)
                yield AgentDone(reason="error", error=fix_error, usage=_finish_usage(turn_usage))
                return
            # loop continues -> re-preview + re-review the fixed state

        logger.info("pipeline_run_metrics %s", metrics)
        yield AgentDone(reason="stop", usage=_finish_usage(turn_usage))
    except Exception as exc:  # noqa: BLE001 - the SSE stream must end with a clean AgentDone,
        # not an uncaught exception mid-generator (chat.py's own outer try/except is a second
        # safety net, but ending cleanly here keeps this module's own contract self-sufficient).
        logger.exception("Product pipeline crashed")
        metrics["skipped_reason"] = f"crash:{type(exc).__name__}"
        logger.info("pipeline_run_metrics %s", metrics)
        yield AgentDone(
            reason="error", error=str(exc) or "Product pipeline error", usage={"pipeline": metrics}
        )
