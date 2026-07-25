"""product_pipeline.run_product_pipeline is what chat.py's _stream_events always runs a turn
through now (see chat.py's call site). These tests fake run_agent_turn/complete_structured/
submit_control_job (module-level names, same monkeypatch convention as test_orchestrator.py)
so the whole brief -> UX -> visual -> implement -> preview -> review -> fix loop can be driven
deterministically without a live provider, Docker daemon, or Postgres.

Every stage always runs (there is no per-stage on/off flag any more) - preview+review only
actually skip when the project type doesn't support preview at all (see _supports_preview),
which most tests below sidestep with a passing fake_submit_control_job rather than a flag.
"""

from __future__ import annotations

import base64
import types
from collections.abc import AsyncIterator

import pytest

from src.services.agent import product_pipeline
from src.services.agent.events import AgentDone, TextDelta, ToolCallRequested, ToolCallResult
from src.services.agent.pipeline_models import (
    BriefOutcome,
    PreviewPageResult,
    PreviewResult,
    ProductBrief,
    ReviewResult,
    ReviewScore,
    UXSpec,
    Viewport,
    VisualDirection,
)
from src.services.agent.tools import WorkspaceTools
from src.services.file_context import ImageAttachment


def _project(project_type: str = "website") -> types.SimpleNamespace:
    return types.SimpleNamespace(name="Demo", description="A demo project", type=project_type)


def _brief(**overrides) -> ProductBrief:
    data = {"product_type": "website", "primary_user_goal": "book a service"}
    data.update(overrides)
    return ProductBrief(**data)


def _passing_review() -> ReviewResult:
    return ReviewResult(
        verdict="pass",
        score=ReviewScore(
            product_completeness=90,
            visual_hierarchy=90,
            originality=90,
            content_quality=90,
            responsive_quality=90,
            accessibility=90,
            functional_honesty=90,
        ),
    )


def _passing_preview(**overrides) -> dict:
    data = {
        "status": "passed",
        "pages": [{"url": "http://app/", "viewport": {"width": 1440, "height": 900}}],
        "fatal_errors": [],
        "warnings": [],
    }
    data.update(overrides)
    return data


async def _drain(gen: AsyncIterator):
    events = []
    async for event in gen:
        events.append(event)
    return events


def _make_complete_structured(
    *,
    brief: BriefOutcome | None = None,
    ux: UXSpec | None = None,
    visual: VisualDirection | None = None,
    reviews: list[ReviewResult] | None = None,
):
    """A response_model-dispatching fake covering all four structured calls the pipeline can
    make (brief/UX/visual/review) - reviews is consumed in order, then repeats the last one
    (or a plain pass) once exhausted."""
    reviews = list(reviews or [])
    calls = {"brief": 0, "ux": 0, "visual": 0, "review": 0}
    seen_images: list[list[ImageAttachment] | None] = []

    async def fake(*, response_model, images=None, **kwargs):
        seen_images.append(images)
        if response_model is BriefOutcome:
            calls["brief"] += 1
            return brief if brief is not None else BriefOutcome(brief=_brief())
        if response_model is UXSpec:
            calls["ux"] += 1
            return ux
        if response_model is VisualDirection:
            calls["visual"] += 1
            return visual
        if response_model is ReviewResult:
            calls["review"] += 1
            if reviews:
                return reviews.pop(0) if len(reviews) > 1 else reviews[0]
            return _passing_review()
        raise AssertionError(f"unexpected response_model {response_model}")

    return fake, calls, seen_images


def _fake_implement(
    *, sets_build_succeeded: bool | None = True, error: str | None = None, text: str = "done"
):
    async def fake(
        *,
        provider_name,
        model,
        api_key,
        workspace,
        system_prompt,
        history,
        user_message,
        images=None,
    ):
        if sets_build_succeeded is not None:
            yield ToolCallRequested(call_id="b1", name="build_project", arguments={})
            ok = sets_build_succeeded
            workspace.build_succeeded = ok
            yield ToolCallResult(call_id="b1", name="build_project", ok=ok, summary="build")
        yield TextDelta(text=text)
        yield AgentDone(reason="error" if error else "stop", error=error)

    return fake


def _fake_submit_control_job_passing(*, action, project_id, timeout_seconds, extra=None):
    """Default preview/build_check double for control-flow tests that don't care about preview
    content, just that it passes cleanly so the loop reaches (or skips past) review predictably."""
    if action == "preview":
        return _passing_preview()
    return {"ok": True}


@pytest.mark.asyncio
async def test_clarifying_questions_stop_before_implementation(tmp_path, monkeypatch):
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    implement_calls = []

    async def fake_implement(**kwargs):
        implement_calls.append(kwargs)
        yield AgentDone(reason="stop")

    async def fake_complete_structured(*, response_model, **kwargs):
        assert response_model is BriefOutcome
        return BriefOutcome(clarifying_questions=["Какая аудитория у сайта?"])

    monkeypatch.setattr(product_pipeline, "run_agent_turn", fake_implement)
    monkeypatch.setattr(product_pipeline, "complete_structured", fake_complete_structured)

    events = await _drain(
        product_pipeline.run_product_pipeline(
            project=_project(),
            provider_name="anthropic",
            model="claude-sonnet-5",
            api_key="key",
            workspace=workspace,
            system_prompt="base",
            history=[],
            user_message="сделай сайт",
        )
    )

    assert implement_calls == []  # never reached implementation (or UX/visual)
    assert any(isinstance(e, TextDelta) and "аудитория" in e.text for e in events)
    final = events[-1]
    assert isinstance(final, AgentDone) and final.reason == "stop"


@pytest.mark.asyncio
async def test_ux_and_visual_are_generated_and_persisted_by_default(tmp_path, monkeypatch):
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    ux = UXSpec(primary_flow=["landing -> booking"])
    visual = VisualDirection(concept_name="Autoshop atelier")
    fake_cs, calls, _ = _make_complete_structured(ux=ux, visual=visual)

    monkeypatch.setattr(product_pipeline, "run_agent_turn", _fake_implement())
    monkeypatch.setattr(product_pipeline, "complete_structured", fake_cs)
    monkeypatch.setattr(product_pipeline, "submit_control_job", _fake_submit_control_job_passing)

    events = await _drain(
        product_pipeline.run_product_pipeline(
            project=_project(),
            provider_name="anthropic",
            model="m",
            api_key="key",
            workspace=workspace,
            system_prompt="base",
            history=[],
            user_message="сделай сайт автосервиса",
        )
    )

    # Preview+review always run too now (a passing preview + a passing review, one pass each).
    assert calls == {"brief": 1, "ux": 1, "visual": 1, "review": 1}
    assert any(isinstance(e, ToolCallRequested) and e.name == "ux_planning" for e in events)
    assert any(isinstance(e, ToolCallRequested) and e.name == "visual_direction" for e in events)
    from src.services.agent import planning_store

    assert planning_store.load_ux(workspace.root) == ux
    assert planning_store.load_visual(workspace.root) == visual
    # The implementation turn's system prompt should have been enriched with all three.
    assert isinstance(events[-1], AgentDone) and events[-1].reason == "stop"


@pytest.mark.asyncio
async def test_bot_projects_skip_preview_and_review_entirely(tmp_path, monkeypatch):
    """Every stage always runs except preview/review, which only ever skip when the project
    type itself doesn't support a browser preview (_supports_preview) - a telegram_bot project
    has no page to screenshot, so there is nothing left to gate with a flag here."""
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    fake_cs, calls, _ = _make_complete_structured()

    monkeypatch.setattr(product_pipeline, "run_agent_turn", _fake_implement())
    monkeypatch.setattr(product_pipeline, "complete_structured", fake_cs)

    events = await _drain(
        product_pipeline.run_product_pipeline(
            project=_project(project_type="telegram_bot"),
            provider_name="anthropic",
            model="m",
            api_key="key",
            workspace=workspace,
            system_prompt="base",
            history=[],
            user_message="сделай бота для записи",
        )
    )

    assert not any(isinstance(e, ToolCallRequested) and e.name == "preview_project" for e in events)
    assert calls["review"] == 0
    final = events[-1]
    assert isinstance(final, AgentDone) and final.reason == "stop"
    from src.services.agent import planning_store

    assert planning_store.load_brief(workspace.root) is not None


@pytest.mark.asyncio
async def test_failed_build_skips_preview_and_review(tmp_path, monkeypatch):
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    fake_cs, calls, _ = _make_complete_structured()

    def fake_submit_control_job(**kwargs):
        raise AssertionError(
            "preview/build_check RPC should never be submitted after a failed build"
        )

    monkeypatch.setattr(
        product_pipeline, "run_agent_turn", _fake_implement(sets_build_succeeded=False)
    )
    monkeypatch.setattr(product_pipeline, "complete_structured", fake_cs)
    monkeypatch.setattr(product_pipeline, "submit_control_job", fake_submit_control_job)

    events = await _drain(
        product_pipeline.run_product_pipeline(
            project=_project(),
            provider_name="anthropic",
            model="m",
            api_key="key",
            workspace=workspace,
            system_prompt="base",
            history=[],
            user_message="сделай сайт" * 5,
        )
    )

    assert calls["review"] == 0
    assert not any(isinstance(e, ToolCallRequested) and e.name == "preview_project" for e in events)
    final = events[-1]
    assert isinstance(final, AgentDone) and final.reason == "stop"


@pytest.mark.asyncio
async def test_preview_requests_multiple_pages_and_a_mobile_viewport(tmp_path, monkeypatch):
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    brief = BriefOutcome(
        brief=_brief(required_pages_or_flows=["личный кабинет", "онлайн-запись", "история визитов"])
    )
    fake_cs, calls, _ = _make_complete_structured(brief=brief)
    seen_targets = []

    def fake_submit_control_job(*, action, project_id, timeout_seconds, extra=None):
        if action == "preview":
            seen_targets.append(extra["targets"])
            return _passing_preview()
        return {"ok": True}

    monkeypatch.setattr(product_pipeline, "run_agent_turn", _fake_implement())
    monkeypatch.setattr(product_pipeline, "complete_structured", fake_cs)
    monkeypatch.setattr(product_pipeline, "submit_control_job", fake_submit_control_job)

    await _drain(
        product_pipeline.run_product_pipeline(
            project=_project(),
            provider_name="anthropic",
            model="m",
            api_key="key",
            workspace=workspace,
            system_prompt="base",
            history=[],
            user_message="кабинет с записью и историей",
        )
    )

    assert len(seen_targets) == 1
    targets = seen_targets[0]
    paths = [t["path"] for t in targets]
    assert paths[0] == "/"
    assert "/cabinet.html" in paths
    assert "/booking.html" in paths
    assert "/history.html" in paths
    # Homepage is checked on both desktop and mobile.
    home_viewports = {
        (t["viewport"]["width"], t["viewport"]["height"]) for t in targets if t["path"] == "/"
    }
    assert (1440, 900) in home_viewports
    assert (390, 844) in home_viewports
    # Every other guessed page is desktop-only (keeps the total check count bounded).
    for t in targets:
        if t["path"] != "/":
            assert t["viewport"] == {"width": 1440, "height": 900}


@pytest.mark.asyncio
async def test_critical_review_triggers_exactly_one_fix_pass_then_passes(tmp_path, monkeypatch):
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    implement_call_count = {"n": 0}

    async def fake_implement(**kwargs):
        implement_call_count["n"] += 1
        workspace.build_succeeded = True
        yield ToolCallResult(call_id="b", name="build_project", ok=True, summary="ok")
        yield AgentDone(reason="stop")

    def fake_submit_control_job(*, action, project_id, timeout_seconds, extra=None):
        assert action == "preview"
        return _passing_preview()

    reviews = [
        ReviewResult(
            verdict="revise",
            critical_issues=["Метатекст «этот сайт создан» виден на публичной странице"],
        ),
        _passing_review(),
    ]
    fake_cs, calls, _ = _make_complete_structured(reviews=reviews)

    monkeypatch.setattr(product_pipeline, "run_agent_turn", fake_implement)
    monkeypatch.setattr(product_pipeline, "complete_structured", fake_cs)
    monkeypatch.setattr(product_pipeline, "submit_control_job", fake_submit_control_job)

    events = await _drain(
        product_pipeline.run_product_pipeline(
            project=_project(),
            provider_name="anthropic",
            model="m",
            api_key="key",
            workspace=workspace,
            system_prompt="base",
            history=[],
            user_message="сделай сайт автосервиса" * 5,
        )
    )

    assert implement_call_count["n"] == 2  # initial implementation + exactly one fix pass
    assert calls["review"] == 2
    fix_texts = [
        e.text for e in events if isinstance(e, TextDelta) and "исправляю" in e.text.lower()
    ]
    assert len(fix_texts) == 1
    final = events[-1]
    assert isinstance(final, AgentDone) and final.reason == "stop"


@pytest.mark.asyncio
async def test_iteration_cap_stops_the_loop_without_erroring(tmp_path, monkeypatch):
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    implement_calls = {"n": 0}

    async def fake_implement(**kwargs):
        implement_calls["n"] += 1
        workspace.build_succeeded = True
        yield AgentDone(reason="stop")

    def fake_submit_control_job(*, action, project_id, timeout_seconds, extra=None):
        return _passing_preview()

    # Always "revise" - the pipeline must still terminate, not loop forever.
    fake_cs, calls, _ = _make_complete_structured(
        reviews=[ReviewResult(verdict="revise", critical_issues=["всё ещё плохо"])]
    )

    monkeypatch.setattr(product_pipeline, "run_agent_turn", fake_implement)
    monkeypatch.setattr(product_pipeline, "complete_structured", fake_cs)
    monkeypatch.setattr(product_pipeline, "submit_control_job", fake_submit_control_job)

    events = await _drain(
        product_pipeline.run_product_pipeline(
            project=_project(),
            provider_name="anthropic",
            model="m",
            api_key="key",
            workspace=workspace,
            system_prompt="base",
            history=[],
            user_message="x" * 10,
        )
    )

    # 1 initial implementation + at most _MAX_REVIEW_ITERATIONS fix passes.
    assert implement_calls["n"] == 3
    final = events[-1]
    assert isinstance(final, AgentDone) and final.reason == "stop"  # gives up, does not error
    assert any(isinstance(e, TextDelta) and "лимит попыток" in e.text for e in events)


@pytest.mark.asyncio
async def test_infra_failure_gets_one_retry_then_gives_up_without_a_fix_pass(tmp_path, monkeypatch):
    """Worker-unreachable/timeout/etc. must not be handed to the coding agent as a "fix this"
    instruction, and must not consume the review-iteration budget - see product_pipeline.py's
    _preview_infra_failure and the user's explicit ask to separate this from content issues."""
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    implement_calls = {"n": 0}
    control_actions: list[str] = []

    async def fake_implement(**kwargs):
        implement_calls["n"] += 1
        workspace.build_succeeded = True
        yield AgentDone(reason="stop")

    def fake_submit_control_job(*, action, project_id, timeout_seconds, extra=None):
        control_actions.append(action)
        if action == "preview":
            return {
                "status": "failed",
                "pages": [],
                "fatal_errors": ["Preview service did not respond - worker may be unavailable"],
                "warnings": [],
            }
        return {"ok": True}

    fake_cs, calls, _ = _make_complete_structured()

    monkeypatch.setattr(product_pipeline, "run_agent_turn", fake_implement)
    monkeypatch.setattr(product_pipeline, "complete_structured", fake_cs)
    monkeypatch.setattr(product_pipeline, "submit_control_job", fake_submit_control_job)

    events = await _drain(
        product_pipeline.run_product_pipeline(
            project=_project(),
            provider_name="anthropic",
            model="m",
            api_key="key",
            workspace=workspace,
            system_prompt="base",
            history=[],
            user_message="z" * 10,
        )
    )

    # Only the ORIGINAL implementation turn ran - infra retries must never trigger
    # compose_fix_user_message/run_agent_turn (that's for content issues only).
    assert implement_calls["n"] == 1
    assert calls["review"] == 0  # never reached an LLM review call either
    assert control_actions.count("preview") == 2  # original attempt + exactly one retry
    assert control_actions.count("build_check") == 1  # one rebuild nudge before the retry
    final = events[-1]
    assert isinstance(final, AgentDone) and final.reason == "stop"  # reported, not an error
    assert any(isinstance(e, TextDelta) and "не смогла запуститься" in e.text for e in events)


@pytest.mark.asyncio
async def test_infra_failure_that_recovers_on_retry_proceeds_to_review(tmp_path, monkeypatch):
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    preview_calls = {"n": 0}

    async def fake_implement(**kwargs):
        workspace.build_succeeded = True
        yield AgentDone(reason="stop")

    def fake_submit_control_job(*, action, project_id, timeout_seconds, extra=None):
        if action == "preview":
            preview_calls["n"] += 1
            if preview_calls["n"] == 1:
                return {
                    "status": "failed",
                    "pages": [],
                    "fatal_errors": ["Image x is not built yet - run build_project first"],
                    "warnings": [],
                }
            return _passing_preview()
        return {"ok": True}

    fake_cs, calls, _ = _make_complete_structured()

    monkeypatch.setattr(product_pipeline, "run_agent_turn", fake_implement)
    monkeypatch.setattr(product_pipeline, "complete_structured", fake_cs)
    monkeypatch.setattr(product_pipeline, "submit_control_job", fake_submit_control_job)

    events = await _drain(
        product_pipeline.run_product_pipeline(
            project=_project(),
            provider_name="anthropic",
            model="m",
            api_key="key",
            workspace=workspace,
            system_prompt="base",
            history=[],
            user_message="w" * 10,
        )
    )

    assert preview_calls["n"] == 2
    assert calls["review"] == 1  # recovered, so a real review did happen
    final = events[-1]
    assert isinstance(final, AgentDone) and final.reason == "stop"


@pytest.mark.asyncio
async def test_review_receives_screenshots_for_non_codex_providers(tmp_path, monkeypatch):
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    shot_dir = workspace.root / ".airuntime" / "preview" / "run123"
    shot_dir.mkdir(parents=True)
    (shot_dir / "home_1440x900.png").write_bytes(b"\x89PNG\r\n fake desktop bytes")
    (shot_dir / "home_390x844.png").write_bytes(b"\x89PNG\r\n fake mobile bytes")

    async def fake_implement(**kwargs):
        workspace.build_succeeded = True
        yield AgentDone(reason="stop")

    def fake_submit_control_job(*, action, project_id, timeout_seconds, extra=None):
        if action == "preview":
            return _passing_preview(
                pages=[
                    {
                        "url": "http://app/",
                        "viewport": {"width": 1440, "height": 900},
                        "screenshot_ref": ".airuntime/preview/run123/home_1440x900.png",
                    },
                    {
                        "url": "http://app/",
                        "viewport": {"width": 390, "height": 844},
                        "screenshot_ref": ".airuntime/preview/run123/home_390x844.png",
                    },
                ]
            )
        return {"ok": True}

    fake_cs, calls, seen_images = _make_complete_structured()

    monkeypatch.setattr(product_pipeline, "run_agent_turn", fake_implement)
    monkeypatch.setattr(product_pipeline, "complete_structured", fake_cs)
    monkeypatch.setattr(product_pipeline, "submit_control_job", fake_submit_control_job)

    await _drain(
        product_pipeline.run_product_pipeline(
            project=_project(),
            provider_name="anthropic",
            model="m",
            api_key="key",
            workspace=workspace,
            system_prompt="base",
            history=[],
            user_message="v" * 10,
        )
    )

    assert calls["review"] == 1
    review_images = seen_images[-1]
    assert review_images is not None
    assert len(review_images) == 2
    decoded = {base64.b64decode(img.data_base64) for img in review_images}
    assert b"\x89PNG\r\n fake desktop bytes" in decoded
    assert b"\x89PNG\r\n fake mobile bytes" in decoded


@pytest.mark.asyncio
async def test_review_screenshot_path_cannot_escape_workspace(tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"not yours")

    escaping = PreviewResult(
        status="passed",
        pages=[
            PreviewPageResult(
                url="http://app/",
                viewport=Viewport(width=1440, height=900),
                screenshot_ref="../secret.png",
            )
        ],
    )
    images = product_pipeline._select_review_screenshots(escaping, workspace_root)
    assert images == []


@pytest.mark.asyncio
async def test_no_secret_value_leaks_into_review_or_metrics(tmp_path, monkeypatch):
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    secret_api_key = "sk-super-secret-do-not-leak"
    seen_user_texts: list[str] = []

    async def fake_implement(**kwargs):
        assert kwargs["api_key"] == secret_api_key
        workspace.build_succeeded = True
        yield AgentDone(reason="stop")

    def fake_submit_control_job(*, action, project_id, timeout_seconds, extra=None):
        if action == "preview":
            return _passing_preview()
        return {"ok": True}

    async def fake_complete_structured(*, response_model, user_text, api_key, **kwargs):
        seen_user_texts.append(user_text)
        assert secret_api_key not in user_text
        if response_model is BriefOutcome:
            return BriefOutcome(brief=_brief())
        if response_model is ReviewResult:
            return _passing_review()
        return None

    monkeypatch.setattr(product_pipeline, "run_agent_turn", fake_implement)
    monkeypatch.setattr(product_pipeline, "complete_structured", fake_complete_structured)
    monkeypatch.setattr(product_pipeline, "submit_control_job", fake_submit_control_job)

    events = await _drain(
        product_pipeline.run_product_pipeline(
            project=_project(),
            provider_name="anthropic",
            model="m",
            api_key=secret_api_key,
            workspace=workspace,
            system_prompt="base",
            history=[],
            user_message="сделай сайт",
        )
    )

    assert seen_user_texts  # sanity: the fakes were actually exercised
    final = events[-1]
    assert isinstance(final, AgentDone)
    assert secret_api_key not in str(final.usage)
    for event in events:
        if isinstance(event, ToolCallResult | TextDelta):
            text = (
                getattr(event, "content", "")
                + getattr(event, "text", "")
                + getattr(event, "summary", "")
            )
            assert secret_api_key not in text


def test_deterministic_review_gate_flags_broken_images():
    preview = PreviewResult.model_validate(
        {
            "status": "passed",
            "pages": [
                {
                    "url": "http://app/",
                    "viewport": {"width": 1440, "height": 900},
                    "broken_images": ['http://app/porsche.jpg (alt="our fleet")'],
                }
            ],
        }
    )
    gate = product_pipeline._deterministic_review_gate(preview)
    assert gate is not None
    assert gate.verdict == "revise"
    assert any("porsche.jpg" in issue for issue in gate.critical_issues)


def test_deterministic_review_gate_blocks_on_fatal_preview_errors():
    preview = PreviewResult(status="failed", fatal_errors=["Could not load http://app/"])
    gate = product_pipeline._deterministic_review_gate(preview)
    assert gate is not None
    assert gate.verdict == "blocked"


def test_deterministic_review_gate_returns_none_when_clean():
    preview = PreviewResult(status="passed")
    assert product_pipeline._deterministic_review_gate(preview) is None


def test_preview_infra_failure_detects_platform_plumbing_errors():
    infra = PreviewResult(status="failed", fatal_errors=["Preview timed out after 90s"])
    assert product_pipeline._preview_infra_failure(infra) is not None

    content = PreviewResult(
        status="failed", fatal_errors=["Could not load http://app/: net::ERR_CONNECTION_REFUSED"]
    )
    assert product_pipeline._preview_infra_failure(content) is None

    not_failed = PreviewResult(status="issues_found", warnings=["something minor"])
    assert product_pipeline._preview_infra_failure(not_failed) is None


def test_review_needs_fix_on_low_score_even_without_critical_issues():
    passing_verdict_low_score = ReviewResult(
        verdict="pass",
        score=ReviewScore(
            product_completeness=90,
            visual_hierarchy=90,
            originality=20,  # below _LOW_SCORE_THRESHOLD
            content_quality=90,
            responsive_quality=90,
            accessibility=90,
            functional_honesty=90,
        ),
    )
    assert product_pipeline._review_needs_fix(passing_verdict_low_score) is True
    assert product_pipeline._review_needs_fix(_passing_review()) is False


def test_resolve_reviewer_same_provider_reuses_turn_key():
    provider, model, key = product_pipeline._resolve_reviewer(
        "anthropic", "claude-sonnet-5", "turn-key"
    )
    assert (provider, model, key) == ("anthropic", "claude-sonnet-5", "turn-key")


def test_resolve_reviewer_pinned_provider_uses_its_own_key(monkeypatch):
    monkeypatch.setattr(product_pipeline.settings, "reviewer_provider", "openai")
    monkeypatch.setattr(product_pipeline.settings, "reviewer_model", "gpt-5.4-mini")
    monkeypatch.setattr(
        product_pipeline,
        "resolve_api_key_for_provider",
        lambda name: "openai-key" if name == "openai" else None,
    )

    provider, model, key = product_pipeline._resolve_reviewer(
        "anthropic", "claude-sonnet-5", "turn-key"
    )
    assert provider == "openai"
    assert model == "gpt-5.4-mini"
    assert key == "openai-key"  # NOT the turn's anthropic key - this was a real bug before the fix


def test_resolve_reviewer_falls_back_when_pinned_provider_has_no_key(monkeypatch):
    monkeypatch.setattr(product_pipeline.settings, "reviewer_provider", "openai")
    monkeypatch.setattr(product_pipeline.settings, "reviewer_model", None)
    monkeypatch.setattr(product_pipeline, "resolve_api_key_for_provider", lambda name: None)
    monkeypatch.setattr(product_pipeline.settings, "openai_api_key", None)

    provider, model, key = product_pipeline._resolve_reviewer(
        "anthropic", "claude-sonnet-5", "turn-key"
    )
    assert (provider, model, key) == ("anthropic", "claude-sonnet-5", "turn-key")


def test_preview_paths_from_brief_matches_known_filenames():
    brief = _brief(required_pages_or_flows=["Личный кабинет с историей", "Онлайн-запись"])
    paths = product_pipeline._preview_paths_from_brief(brief)
    assert paths[0] == "/"
    assert "/cabinet.html" in paths
    assert "/history.html" in paths
    assert "/booking.html" in paths
    assert len(paths) <= 4


def test_preview_paths_from_brief_handles_no_brief():
    assert product_pipeline._preview_paths_from_brief(None) == ["/"]
