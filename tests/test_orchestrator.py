"""Regression coverage for orchestrator.py's per-subtask commit (2026-07-23): a real multi-part
run can take tens of minutes, and before this the project's Files/version history stayed
completely empty the whole time - only one commit landed, after the *entire* turn (all subtasks)
finished - even though earlier parts had genuinely already written real files minutes before.
"""

from collections.abc import AsyncIterator

import pytest

from src.core.config import settings
from src.services.agent import orchestrator
from src.services.agent.events import AgentDone, TextDelta
from src.services.agent.orchestrator import Subtask, run_agent_turn
from src.services.agent.tools import WorkspaceTools
from src.services.project_git import ProjectGitError


class _FakeSubSession:
    """Stands in for CodingAgentSession - yields one text delta then AgentDone."""

    def __init__(self, *, provider_name, model, api_key, workspace, system_prompt) -> None:
        self.system_prompt = system_prompt
        self.last_user_message: str | None = None

    async def run(self, *, history, user_message, images=None) -> AsyncIterator:
        self.last_user_message = user_message
        yield TextDelta(text=f"did: {user_message}")
        yield AgentDone(reason="stop")


@pytest.fixture(autouse=True)
def _enable_orchestrator(monkeypatch):
    monkeypatch.setattr(settings, "enable_agent_orchestrator", True)


async def _drain(workspace, monkeypatch, subtasks, commit_calls):
    async def fake_plan_subtasks(*, model, user_message):
        return subtasks

    def fake_commit_snapshot(project_dir, *, message):
        commit_calls.append((project_dir, message))
        return "abc1234"

    monkeypatch.setattr(orchestrator, "_plan_subtasks", fake_plan_subtasks)
    monkeypatch.setattr(orchestrator, "CodingAgentSession", _FakeSubSession)
    monkeypatch.setattr(orchestrator, "commit_snapshot", fake_commit_snapshot)

    events = []
    async for event in run_agent_turn(
        provider_name="openai",
        model="gpt-5.4-mini",
        api_key="test-key",
        workspace=workspace,
        system_prompt="base prompt",
        history=[],
        user_message="сделай сайт с личным кабинетом и telegram-ботом" * 3,
    ):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_commits_after_every_subtask_not_just_at_the_end(tmp_path, monkeypatch):
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    subtasks = [
        Subtask(title="Лендинг", instructions="сделай лендинг"),
        Subtask(title="Личный кабинет", instructions="сделай кабинет"),
        Subtask(title="Telegram-бот", instructions="сделай бота"),
    ]
    commit_calls: list[tuple] = []

    await _drain(workspace, monkeypatch, subtasks, commit_calls)

    assert len(commit_calls) == 3
    assert [root for root, _ in commit_calls] == [tmp_path] * 3
    assert commit_calls[0][1] == "Лендинг (часть 1/3)"
    assert commit_calls[1][1] == "Личный кабинет (часть 2/3)"
    assert commit_calls[2][1] == "Telegram-бот (часть 3/3)"


@pytest.mark.asyncio
async def test_a_git_error_on_one_subtask_does_not_abort_the_turn(tmp_path, monkeypatch):
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    subtasks = [
        Subtask(title="Часть А", instructions="а"),
        Subtask(title="Часть Б", instructions="б"),
    ]

    async def fake_plan_subtasks(*, model, user_message):
        return subtasks

    calls: list[str] = []

    def flaky_commit_snapshot(project_dir, *, message):
        calls.append(message)
        if len(calls) == 1:
            raise ProjectGitError("lock busy")
        return "def5678"

    monkeypatch.setattr(orchestrator, "_plan_subtasks", fake_plan_subtasks)
    monkeypatch.setattr(orchestrator, "CodingAgentSession", _FakeSubSession)
    monkeypatch.setattr(orchestrator, "commit_snapshot", flaky_commit_snapshot)

    events = []
    async for event in run_agent_turn(
        provider_name="openai",
        model="gpt-5.4-mini",
        api_key="test-key",
        workspace=workspace,
        system_prompt="base prompt",
        history=[],
        user_message="сделай сайт с личным кабинетом и telegram-ботом" * 3,
    ):
        events.append(event)

    # Both subtasks still ran (the git error on part 1 didn't abort part 2), and the turn as a
    # whole still reports success.
    assert len(calls) == 2
    final = events[-1]
    assert isinstance(final, AgentDone)
    assert final.reason == "stop"


@pytest.mark.asyncio
async def test_subtask_keeps_original_user_message_and_deploy_contract(tmp_path, monkeypatch):
    workspace = WorkspaceTools(tmp_path, project_id="proj-1")
    original = "сделай сайт кофейни с меню и telegram-ботом заказов" * 3
    subtasks = [
        Subtask(title="Лендинг", instructions="сделай лендинг кофейни"),
        Subtask(title="Бот", instructions="сделай бота заказов"),
    ]
    sessions: list[_FakeSubSession] = []
    commit_calls: list[tuple] = []

    async def fake_plan_subtasks(*, model, user_message):
        return subtasks

    def session_factory(**kwargs):
        session = _FakeSubSession(**kwargs)
        sessions.append(session)
        return session

    monkeypatch.setattr(orchestrator, "_plan_subtasks", fake_plan_subtasks)
    monkeypatch.setattr(orchestrator, "CodingAgentSession", session_factory)
    monkeypatch.setattr(
        orchestrator, "commit_snapshot", lambda *a, **k: commit_calls.append(k) or "abc"
    )

    async for _ in run_agent_turn(
        provider_name="openai",
        model="gpt-5.4-mini",
        api_key="test-key",
        workspace=workspace,
        system_prompt="base prompt",
        history=[],
        user_message=original,
    ):
        pass

    assert len(sessions) == 2
    for session in sessions:
        assert original in (session.last_user_message or "")
        assert "Исходный запрос пользователя" in (session.last_user_message or "")
        assert "Traefik" in session.system_prompt
        assert "порт 80" in session.system_prompt


def test_planning_prompt_forbids_infra_split():
    assert "НИКОГДА не выделяй отдельную часть про инфраструктуру" in orchestrator._PLANNING_PROMPT
    assert "Traefik" in orchestrator._PLANNING_PROMPT


def test_planning_prompt_prefers_landing_vs_cabinet_split():
    assert "лендинг и кабинет" in orchestrator._PLANNING_PROMPT
    assert "не один index.html" in orchestrator._PLANNING_PROMPT
    assert "настройка бота" in orchestrator._PLANNING_PROMPT
