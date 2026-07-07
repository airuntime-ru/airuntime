import uuid

import pytest

from src.core.config import settings
from src.db.models.project import Project
from src.services.artifacts import ArtifactError, generate_project_artifact


def test_generate_website_artifact_escapes_prompt(tmp_path, monkeypatch, db):
    monkeypatch.setattr(settings, "generated_projects_dir", str(tmp_path))
    project = Project(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        type="website",
        name="<Demo>",
        description="Landing for customers",
    )

    path = generate_project_artifact(db, project, "<script>alert(1)</script>; Fast checkout")

    index_html = (path / "public" / "index.html").read_text(encoding="utf-8")
    assert (path / "Dockerfile").exists()
    assert "&lt;Demo&gt;" in index_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in index_html
    assert "<script>alert(1)</script>" not in index_html


def test_telegram_bot_requires_token_secret(tmp_path, monkeypatch, db):
    monkeypatch.setattr(settings, "generated_projects_dir", str(tmp_path))
    project = Project(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        type="telegram_bot",
        name="Support Bot",
        description="Answers customer questions",
    )

    with pytest.raises(ArtifactError, match="TELEGRAM_BOT_TOKEN"):
        generate_project_artifact(db, project, "Launch the bot")
