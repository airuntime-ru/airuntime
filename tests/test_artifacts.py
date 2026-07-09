import uuid

import pytest

from src.core.config import settings
from src.db.models.project import Project
from src.db.models.secret import Secret
from src.db.models.user import User
from src.services.artifacts import ArtifactError, _telegram_token, generate_project_artifact
from src.services.secrets import encrypt_secret


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


def test_telegram_token_secret_lookup_accepts_human_key_names(db):
    user = User(
        id=uuid.uuid4(),
        email="secret-lookup@airuntime.dev",
        password_hash=None,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    project = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        type="telegram_bot",
        name="Support Bot",
        description="Answers customer questions",
    )
    db.add(project)
    db.flush()
    db.add(
        Secret(
            project_id=project.id,
            key="Telegram Bot Token",
            encrypted_value=encrypt_secret("123:abc"),
        )
    )
    db.flush()

    assert _telegram_token(db, project) == "123:abc"
