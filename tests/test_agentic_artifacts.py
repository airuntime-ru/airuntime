import asyncio
import json
import uuid

import pytest

from src.core.config import settings
from src.db.models.project import Project
from src.services import agentic_artifacts
from src.services.agentic_artifacts import (
    ArtifactError,
    generate_agentic_artifact,
    generate_project_artifact_agentic,
)


class FakeProvider:
    def __init__(self, text: str) -> None:
        self.text = text

    async def stream(self, *, messages, model, tools):
        assert messages
        assert model
        assert tools == []
        midpoint = max(1, len(self.text) // 2)
        yield self.text[:midpoint]
        yield self.text[midpoint:]


class DummyDb:
    def add(self, item) -> None:
        self.item = item


class EmptyQuery:
    def filter(self, *args, **kwargs):
        return self

    def all(self) -> list:
        return []


class TokenlessDb(DummyDb):
    def query(self, model):
        return EmptyQuery()


def _project(project_type: str = "website") -> Project:
    return Project(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        type=project_type,
        name="Demo Project",
        description="A bright product launch",
    )


def test_agentic_website_manifest_writes_project_files(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "generated_projects_dir", str(tmp_path))
    manifest = {
        "summary": "Generated site",
        "files": [
            {
                "path": "public/index.html",
                "content": "<!doctype html><html><body><h1>Demo</h1></body></html>",
            },
            {"path": "public/styles.css", "content": "body{font-family:sans-serif}"},
        ],
    }
    monkeypatch.setattr(
        agentic_artifacts, "get_provider", lambda provider_name: FakeProvider(json.dumps(manifest))
    )

    path = asyncio.run(generate_agentic_artifact(DummyDb(), _project("website"), "Build a site"))

    assert (path / "public" / "index.html").exists()
    assert (path / "public" / "styles.css").exists()
    assert (path / "Dockerfile").read_text(encoding="utf-8").startswith("FROM nginx")
    meta = json.loads((path / ".airuntime" / "manifest.json").read_text(encoding="utf-8"))
    assert meta["source"].startswith("ai:")


def test_agentic_manifest_rejects_unsafe_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "generated_projects_dir", str(tmp_path))
    manifest = {
        "files": [
            {"path": "../escape.txt", "content": "bad"},
            {"path": "public/index.html", "content": "ok"},
        ]
    }
    monkeypatch.setattr(
        agentic_artifacts, "get_provider", lambda provider_name: FakeProvider(json.dumps(manifest))
    )

    with pytest.raises(ArtifactError, match="Blocked|Unsafe"):
        asyncio.run(generate_agentic_artifact(DummyDb(), _project("website"), "Build a site"))


def test_agentic_generation_falls_back_when_provider_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "generated_projects_dir", str(tmp_path))

    class FailingProvider:
        async def stream(self, *, messages, model, tools):
            raise RuntimeError("provider down")
            yield ""

    monkeypatch.setattr(agentic_artifacts, "get_provider", lambda provider_name: FailingProvider())
    project = _project("website")

    path = asyncio.run(generate_project_artifact_agentic(DummyDb(), project, "Build a site"))

    assert (path / "public" / "index.html").exists()
    assert "fallback" in (path / ".airuntime" / "manifest.json").read_text(encoding="utf-8")
    assert "fallback used" in project.logs


def test_agentic_telegram_manifest_requires_token_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "generated_projects_dir", str(tmp_path))
    manifest = {"files": [{"path": "app.py", "content": "print('missing env')"}]}
    monkeypatch.setattr(
        agentic_artifacts, "get_provider", lambda provider_name: FakeProvider(json.dumps(manifest))
    )

    with pytest.raises(ArtifactError, match="TELEGRAM_BOT_TOKEN"):
        asyncio.run(generate_agentic_artifact(DummyDb(), _project("telegram_bot"), "Build bot"))


def test_agentic_telegram_generation_requires_token_before_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "generated_projects_dir", str(tmp_path))

    class FailingProvider:
        async def stream(self, *, messages, model, tools):
            raise RuntimeError("provider down")
            yield ""

    monkeypatch.setattr(agentic_artifacts, "get_provider", lambda provider_name: FailingProvider())

    with pytest.raises(ArtifactError, match="TELEGRAM_BOT_TOKEN"):
        asyncio.run(
            generate_project_artifact_agentic(TokenlessDb(), _project("telegram_bot"), "Build bot")
        )
