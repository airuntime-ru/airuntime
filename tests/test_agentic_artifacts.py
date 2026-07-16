import asyncio
import uuid

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
        "edit_file",
        {"path": "app.py", "old_text": "print('unique')", "new_text": "print('changed')"},
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


def test_workspace_tools_request_service_arbitrary_image(tmp_path):
    tools = WorkspaceTools(tmp_path, project_id="11111111-2222-3333-4444-555555555555")
    result = tools.call(
        "request_service",
        {
            "kind": "search",
            "reason": "нужен полнотекстовый поиск",
            "image": "elasticsearch:8.15.0",
            "env": {"discovery.type": "single-node"},
            "data_path": "/usr/share/elasticsearch/data",
        },
    )
    assert result.ok
    assert "airuntime-11111111-search" in result.summary
    assert len(tools.requested_services) == 1
    request = tools.requested_services[0]
    assert request.kind == "search"
    assert request.image == "elasticsearch:8.15.0"
    assert request.env == {"discovery.type": "single-node"}
    assert request.data_path == "/usr/share/elasticsearch/data"


def test_workspace_tools_request_service_rejects_unknown_kind_without_image(tmp_path):
    tools = WorkspaceTools(tmp_path)
    result = tools.call("request_service", {"kind": "search", "reason": "нужен поиск"})
    assert not result.ok
    assert not tools.requested_services


def test_workspace_tools_request_service_preset_needs_no_image(tmp_path):
    tools = WorkspaceTools(tmp_path)
    result = tools.call("request_service", {"kind": "postgres", "reason": "нужна БД"})
    assert result.ok
    assert tools.requested_services[0].image is None


def test_workspace_tools_build_project_calls_control_queue(tmp_path, monkeypatch):
    import src.services.docker_control_queue as control_queue

    calls = []

    def fake_submit_control_job(*, action, project_id, timeout_seconds):
        calls.append((action, project_id, timeout_seconds))
        return {"ok": True, "log": "Build succeeded: airuntime-generated-site:latest"}

    monkeypatch.setattr(control_queue, "submit_control_job", fake_submit_control_job)

    tools = WorkspaceTools(tmp_path, project_id="project-123")
    result = tools.call("build_project", {})

    assert result.ok
    assert "Build succeeded" in result.content
    assert calls == [("build_check", "project-123", 180)]


def test_workspace_tools_build_project_reports_failure(tmp_path, monkeypatch):
    import src.services.docker_control_queue as control_queue

    monkeypatch.setattr(
        control_queue,
        "submit_control_job",
        lambda **kwargs: {"ok": False, "log": "SyntaxError: line 3"},
    )

    tools = WorkspaceTools(tmp_path, project_id="project-123")
    result = tools.call("build_project", {})

    assert not result.ok
    assert "SyntaxError" in result.content


def test_workspace_tools_build_project_without_project_id(tmp_path):
    tools = WorkspaceTools(tmp_path)
    result = tools.call("build_project", {})
    assert not result.ok


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


def test_ensure_required_files_mixed_requires_both_entry_files(tmp_path):
    project = _project("mixed")
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")
    with pytest.raises(ArtifactError, match="app.py"):
        ensure_required_files(project, tmp_path)

    (tmp_path / "app.py").write_text("os.environ['TELEGRAM_BOT_TOKEN']", encoding="utf-8")
    ensure_required_files(project, tmp_path)

    dockerfile = (tmp_path / "Dockerfile").read_text(encoding="utf-8")
    assert "nginx" in dockerfile
    assert "app.py" in dockerfile


def test_generate_fallback_artifact_mixed_produces_both_without_wiping_either(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "generated_projects_dir", str(tmp_path))
    project = _project("mixed")
    path = generate_fallback_artifact(DummyDb(), project, "Сайт и бот для студии")
    assert (path / "public" / "index.html").exists()
    assert (path / "app.py").exists()
    assert (path / "requirements.txt").exists()
    dockerfile = (path / "Dockerfile").read_text(encoding="utf-8")
    assert "nginx" in dockerfile
    assert "app.py" in dockerfile


class FakeProvider:
    def __init__(self, turns):
        self._turns = turns
        self.call_count = 0

    def supports_tools(self):
        return True

    def build_messages(self, history, user_message, *, images=None):
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
    import src.services.agent.loop as loop_module

    monkeypatch.setattr(loop_module, "MAX_ITERATIONS", 3)

    looping_turn = [
        TurnFinished(
            stop_reason="tool_use",
            wire_message={"role": "assistant", "content": "..."},
            tool_calls=[ToolCallRequested(call_id="c", name="list_files", arguments={"path": "."})],
        )
    ]
    fake = FakeProvider([looping_turn for _ in range(3)])
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
