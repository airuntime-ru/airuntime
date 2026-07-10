import asyncio
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from src.core.config import settings
from src.db.models.project import Project
from src.services.agent.events import TextDelta, ToolCallRequested, ToolCallResult, TurnFinished
from src.services.agent.loop import CodingAgentSession
from src.services.agent.tools import WorkspaceTools
from src.services.agentic_artifacts import ensure_required_files, generate_fallback_artifact
from src.services.artifacts import ArtifactError
from src.services.workspace import WorkspaceError, project_dir


def _project(project_type: str = "website") -> Project:
    return Project(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        type=project_type,
        name="Demo Project",
        description="A bright product launch",
    )


class DummyDb:
    def add(self, item) -> None:
        self.item = item


def test_workspace_tools_write_then_read_roundtrip(tmp_path):
    tools = WorkspaceTools(tmp_path)
    result = tools.call("write_file", {"path": "public/index.html", "content": "<h1>hi</h1>"})
    assert result.ok
    assert "public/index.html" in tools.touched_files

    read = tools.call("read_file", {"path": "public/index.html"})
    assert read.ok
    assert read.content == "<h1>hi</h1>"


def test_workspace_tools_edit_file_requires_unique_match(tmp_path):
    (tmp_path / "app.py").write_text("print('a')\nprint('a')\n", encoding="utf-8")
    tools = WorkspaceTools(tmp_path)

    ambiguous = tools.call(
        "edit_file", {"path": "app.py", "old_text": "print('a')", "new_text": "print('b')"}
    )
    assert not ambiguous.ok
    assert "not unique" in ambiguous.summary

    (tmp_path / "app.py").write_text("print('unique')\n", encoding="utf-8")
    ok = tools.call(
        "edit_file", {"path": "app.py", "old_text": "print('unique')", "new_text": "print('changed')"}
    )
    assert ok.ok
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "print('changed')\n"


def test_workspace_tools_rejects_path_escape(tmp_path):
    tools = WorkspaceTools(tmp_path)
    result = tools.call("write_file", {"path": "../escape.txt", "content": "bad"})
    assert not result.ok

    from src.services.workspace import resolve_in_workspace

    with pytest.raises(WorkspaceError):
        resolve_in_workspace(tmp_path, "../../etc/passwd")


def test_workspace_tools_list_files(tmp_path):
    tools = WorkspaceTools(tmp_path)
    tools.call("write_file", {"path": "public/index.html", "content": "hi"})
    tools.call("write_file", {"path": "public/styles.css", "content": "body{}"})
    listing = tools.call("list_files", {"path": "."})
    assert listing.ok
    assert "public/index.html" in listing.content
    assert "public/styles.css" in listing.content


def test_ensure_required_files_injects_default_dockerfile(tmp_path):
    project = _project("website")
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")

    ensure_required_files(project, tmp_path)

    assert (tmp_path / "Dockerfile").read_text(encoding="utf-8").startswith("FROM nginx")


def test_ensure_required_files_raises_when_entry_file_missing(tmp_path):
    project = _project("website")
    with pytest.raises(ArtifactError):
        ensure_required_files(project, tmp_path)


def test_ensure_required_files_telegram_requires_token_env_read(tmp_path):
    project = _project("telegram_bot")
    (tmp_path / "app.py").write_text("print('missing env')", encoding="utf-8")
    with pytest.raises(ArtifactError, match="TELEGRAM_BOT_TOKEN"):
        ensure_required_files(project, tmp_path)


def test_generate_fallback_artifact_produces_required_files(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "generated_projects_dir", str(tmp_path))
    project = _project("website")
    path = generate_fallback_artifact(DummyDb(), project, "Build a site")
    assert (path / "public" / "index.html").exists()
    assert path == project_dir(project.id)


class FakeProvider:
    def __init__(self, turns):
        self._turns = turns
        self.call_count = 0

    def supports_tools(self):
        return True

    def build_messages(self, history, user_message):
        return [*history, {"role": "user", "content": user_message}]

    def build_tool_result_messages(self, results):
        return [{"role": "tool", "content": r.content} for r in results]

    async def stream_turn(self, *, system_prompt, messages, tools, model, api_key):
        events = self._turns[self.call_count]
        self.call_count += 1
        for event in events:
            yield event


def _patch_provider(monkeypatch, fake):
    monkeypatch.setattr("src.services.agent.loop.get_agent_provider", lambda name: fake)


def test_agent_session_writes_a_file_then_stops(tmp_path, monkeypatch):
    turn_one = [
        TextDelta(text="Creating page. "),
        TurnFinished(
            stop_reason="tool_use",
            wire_message={"role": "assistant", "content": "..."},
            tool_calls=[
                ToolCallRequested(
                    call_id="call_1",
                    name="write_file",
                    arguments={"path": "public/index.html", "content": "<h1>Hi</h1>"},
                )
            ],
        ),
    ]
    turn_two = [
        TextDelta(text="Done!"),
        TurnFinished(stop_reason="stop", wire_message={"role": "assistant", "content": "Done!"}),
    ]
    fake = FakeProvider([turn_one, turn_two])
    _patch_provider(monkeypatch, fake)

    workspace = WorkspaceTools(tmp_path)
    session = CodingAgentSession(
        provider_name="openai",
        model="gpt-4o-mini",
        api_key="test-key",
        workspace=workspace,
        system_prompt="test",
    )

    async def _run():
        events = []
        async for event in session.run(history=[], user_message="Build a site"):
            events.append(event)
        return events

    events = asyncio.run(_run())

    assert (tmp_path / "public" / "index.html").exists()
    assert any(isinstance(e, ToolCallResult) and e.ok for e in events)
    text = "".join(e.text for e in events if isinstance(e, TextDelta))
    assert "Done" in text
    assert fake.call_count == 2


def test_agent_session_stops_at_max_iterations(tmp_path, monkeypatch):
    looping_turn = [
        TurnFinished(
            stop_reason="tool_use",
            wire_message={"role": "assistant", "content": "..."},
            tool_calls=[ToolCallRequested(call_id="c", name="list_files", arguments={"path": "."})],
        )
    ]
    fake = FakeProvider([looping_turn for _ in range(20)])
    _patch_provider(monkeypatch, fake)

    workspace = WorkspaceTools(tmp_path)
    session = CodingAgentSession(
        provider_name="openai",
        model="gpt-4o-mini",
        api_key="test-key",
        workspace=workspace,
        system_prompt="test",
    )

    async def _run():
        last = None
        async for event in session.run(history=[], user_message="Build a site"):
            last = event
        return last

    final_event = asyncio.run(_run())

    from src.services.agent.events import AgentDone

    assert isinstance(final_event, AgentDone)
    assert final_event.reason == "max_iterations"


def test_agent_session_surfaces_provider_error(tmp_path, monkeypatch):
    fake = FakeProvider([[TurnFinished(stop_reason="error", error="API key is not configured")]])
    _patch_provider(monkeypatch, fake)

    workspace = WorkspaceTools(tmp_path)
    session = CodingAgentSession(
        provider_name="openai",
        model="gpt-4o-mini",
        api_key="",
        workspace=workspace,
        system_prompt="test",
    )

    async def _run():
        events = []
        async for event in session.run(history=[], user_message="Build a site"):
            events.append(event)
        return events

    events = asyncio.run(_run())

    from src.services.agent.events import AgentDone

    done = [e for e in events if isinstance(e, AgentDone)][0]
    assert done.reason == "error"
    assert "API key" in done.error
