import json
from types import SimpleNamespace

from tests.conftest import auth_tokens


class _FakeConversationService:
    async def stream_reply(self, *, chat_id: str, user_message: str):
        yield "Готово: "
        yield user_message[:20]


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_code_verify_and_me(client):
    email = "user@airuntime.dev"
    issued = client.post("/api/v1/auth/request-code", json={"email": email})
    assert issued.status_code == 200
    code = issued.json()["dev_code"]
    assert code

    verified = client.post("/api/v1/auth/verify-code", json={"email": email, "code": code})
    assert verified.status_code == 200
    tokens = verified.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == email
    assert body["is_verified"] is True
    assert body["credits_balance"] == 1_000_000_000


def test_projects_crud(client):
    headers = auth_tokens(client, "builder@airuntime.dev")

    create = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"type": "website", "name": "Landing", "description": "Marketing site"},
    )
    assert create.status_code == 200
    project = create.json()
    assert project["name"] == "Landing"

    listed = client.get("/api/v1/projects", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    patch = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=headers,
        json={"description": "Updated description"},
    )
    assert patch.status_code == 200
    assert patch.json()["description"] == "Updated description"

    subdomain_patch = client.patch(
        f"/api/v1/projects/{project['id']}",
        headers=headers,
        json={"deploy_subdomain": "my-landing"},
    )
    assert subdomain_patch.status_code == 200
    body = subdomain_patch.json()
    assert body["deploy_subdomain"] == "my-landing"
    assert body["planned_site_url"] == "https://my-landing.airuntime.ru"


def test_project_type_is_inferred_when_create_payload_has_no_type(client):
    headers = auth_tokens(client, "intent@airuntime.dev")

    create = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "Support automation",
            "description": "Telegram bot for client requests and notifications",
        },
    )

    assert create.status_code == 200
    assert create.json()["type"] == "telegram_bot"


def test_project_type_is_inferred_from_russian_bot_prompt(client):
    headers = auth_tokens(client, "intent-ru@airuntime.dev")

    create = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "ТГ помощник",
            "description": "напиши тг бота который на все сообщения отвечает привет",
        },
    )

    assert create.status_code == 200
    assert create.json()["type"] == "telegram_bot"


def test_project_logs_endpoint(client):
    headers = auth_tokens(client, "logs@airuntime.dev")

    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"type": "website", "name": "Logs Project", "description": ""},
    ).json()

    response = client.get(f"/api/v1/projects/{project['id']}/logs", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["project_logs"] == ""
    assert body["deployment_status"] is None
    assert body["runtime_logs"] == ""


def test_chat_messages_list(client):
    headers = auth_tokens(client, "chat@airuntime.dev")

    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"type": "telegram_bot", "name": "Support Bot", "description": ""},
    ).json()

    chat = client.post(f"/api/v1/projects/{project['id']}/chats", headers=headers).json()
    message = client.post(
        f"/api/v1/projects/{project['id']}/chats/{chat['id']}/messages",
        headers=headers,
        json={"content": "Hello AIRuntime"},
    )
    assert message.status_code == 200

    listed = client.get(
        f"/api/v1/projects/{project['id']}/chats/{chat['id']}/messages",
        headers=headers,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["content_markdown"] == "Hello AIRuntime"


def test_chat_file_upload_and_message_with_attachment(client):
    headers = auth_tokens(client, "files@airuntime.dev")

    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"type": "website", "name": "Files Project", "description": ""},
    ).json()
    chat = client.post(f"/api/v1/projects/{project['id']}/chats", headers=headers).json()

    upload = client.post(
        f"/api/v1/projects/{project['id']}/chats/{chat['id']}/files",
        headers=headers,
        files={"file": ("notes.txt", b"build a landing page", "text/plain")},
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]
    assert upload.json()["original_filename"] == "notes.txt"

    message = client.post(
        f"/api/v1/projects/{project['id']}/chats/{chat['id']}/messages",
        headers=headers,
        json={"content": "Use this spec", "attachment_ids": [file_id]},
    )
    assert message.status_code == 200
    body = message.json()
    assert body["attachments"][0]["id"] == file_id

    listed = client.get(
        f"/api/v1/projects/{project['id']}/chats/{chat['id']}/files", headers=headers
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_secret_key_is_normalized_for_telegram_token(client):
    headers = auth_tokens(client, "secret-normalize@airuntime.dev")

    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"type": "telegram_bot", "name": "Secret Bot", "description": ""},
    ).json()

    created = client.post(
        f"/api/v1/projects/{project['id']}/secrets",
        headers=headers,
        json={"key": "telegram bot token", "value": "123:abc"},
    )

    assert created.status_code == 200
    assert created.json()["key"] == "TELEGRAM_BOT_TOKEN"


def test_telegram_token_secret_sets_public_bot_url(client, monkeypatch):
    from src.api.routers import secrets as secrets_router

    headers = auth_tokens(client, "secret-telegram-url@airuntime.dev")
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"type": "telegram_bot", "name": "Secret URL Bot", "description": ""},
    ).json()

    monkeypatch.setattr(
        secrets_router,
        "fetch_bot_profile",
        lambda token: SimpleNamespace(public_url="https://t.me/secret_url_bot"),
    )

    created = client.post(
        f"/api/v1/projects/{project['id']}/secrets",
        headers=headers,
        json={
            "key": "telegram bot token",
            "value": "12345678901234567890:abcdefghijklmnopqrstuvwxyz",
        },
    )

    assert created.status_code == 200
    assert created.json()["url"] == "https://t.me/secret_url_bot"

    refreshed = client.get(f"/api/v1/projects/{project['id']}", headers=headers)
    assert refreshed.json()["deployment_url"] == "https://t.me/secret_url_bot"


def test_telegram_token_save_sets_public_bot_url(client, monkeypatch):
    from src.api.routers import telegram as telegram_router

    headers = auth_tokens(client, "telegram-url@airuntime.dev")
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"type": "telegram_bot", "name": "URL Bot", "description": ""},
    ).json()

    monkeypatch.setattr(
        telegram_router,
        "fetch_bot_profile",
        lambda token: SimpleNamespace(public_url="https://t.me/url_bot"),
    )

    saved = client.post(
        f"/api/v1/projects/{project['id']}/telegram/token",
        headers=headers,
        json={"bot_token": "12345678901234567890:abc"},
    )

    assert saved.status_code == 200
    assert saved.json()["url"] == "https://t.me/url_bot"

    refreshed = client.get(f"/api/v1/projects/{project['id']}", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["deployment_url"] == "https://t.me/url_bot"


def test_telegram_start_refreshes_public_bot_url_from_token(client, monkeypatch):
    from src.api.routers import telegram as telegram_router

    headers = auth_tokens(client, "telegram-start-url@airuntime.dev")
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"type": "telegram_bot", "name": "Start URL Bot", "description": ""},
    ).json()
    client.post(
        f"/api/v1/projects/{project['id']}/secrets",
        headers=headers,
        json={"key": "telegram bot token", "value": "12345678901234567890:abc"},
    )

    monkeypatch.setattr(
        telegram_router,
        "fetch_bot_profile",
        lambda token: SimpleNamespace(public_url="https://t.me/start_url_bot"),
    )

    started = client.post(f"/api/v1/projects/{project['id']}/telegram/start", headers=headers)

    assert started.status_code == 200
    assert started.json()["url"] == "https://t.me/start_url_bot"

    refreshed = client.get(f"/api/v1/projects/{project['id']}", headers=headers)
    assert refreshed.json()["deployment_url"] == "https://t.me/start_url_bot"


def test_stream_prompt_generates_artifact_and_queues_deployment(
    client, monkeypatch, tmp_path
):
    from src.api.routers import chat as chat_router

    generated = []
    deployments = []

    async def fake_generate_project_artifact(db, project, prompt):
        generated.append((project.id, prompt))
        return tmp_path / "artifact"

    def fake_create_deployment(db, project):
        deployments.append(project.id)
        return None

    monkeypatch.setattr(chat_router, "ConversationService", _FakeConversationService)
    monkeypatch.setattr(
        chat_router, "generate_project_artifact_agentic", fake_generate_project_artifact
    )
    monkeypatch.setattr(chat_router, "create_deployment_for_project", fake_create_deployment)

    headers = auth_tokens(client, "stream@airuntime.dev")
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"type": "website", "name": "Prompt Site", "description": ""},
    ).json()
    chat = client.post(f"/api/v1/projects/{project['id']}/chats", headers=headers).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/chats/{chat['id']}/stream",
        headers=headers,
        json={"content": "Сделай светлый лендинг для студии"},
    )

    assert response.status_code == 200
    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: {")
    ]
    chunks = [payload["chunk"] for payload in payloads if "chunk" in payload]
    statuses = [payload["status"]["phase"] for payload in payloads if "status" in payload]
    assert "artifact" in statuses
    assert "deploy" in statuses
    assert any("Сайт собран и поставлен в очередь на запуск" in chunk for chunk in chunks)
    assert "data: [DONE]" in response.text
    assert generated
    assert deployments == [generated[0][0]]

    messages = client.get(
        f"/api/v1/projects/{project['id']}/chats/{chat['id']}/messages",
        headers=headers,
    ).json()
    assert any(
        "Сайт собран и поставлен в очередь на запуск" in message["content_markdown"]
        for message in messages
    )

    updated = client.get(f"/api/v1/projects/{project['id']}", headers=headers).json()
    assert updated["status"] == "ready"


def test_stream_subdomain_from_prompt_sets_deploy_subdomain(client, monkeypatch, tmp_path):
    from src.api.routers import chat as chat_router

    deployments: list[str | None] = []

    async def fake_generate_project_artifact(db, project, prompt):
        return tmp_path / "artifact"

    def fake_create_deployment(db, project):
        deployments.append(project.deploy_subdomain)
        return None

    monkeypatch.setattr(chat_router, "ConversationService", _FakeConversationService)
    monkeypatch.setattr(
        chat_router, "generate_project_artifact_agentic", fake_generate_project_artifact
    )
    monkeypatch.setattr(chat_router, "create_deployment_for_project", fake_create_deployment)

    headers = auth_tokens(client, "subdomain@airuntime.dev")
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"type": "website", "name": "Subdomain Site", "description": ""},
    ).json()
    chat = client.post(f"/api/v1/projects/{project['id']}/chats", headers=headers).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/chats/{chat['id']}/stream",
        headers=headers,
        json={"content": "Собери лендинг и запусти на https://test.airuntime.ru"},
    )

    assert response.status_code == 200
    assert any("URL: https://test.airuntime.ru" in line for line in response.text.splitlines())
    assert deployments == ["test"]


def test_stream_prompt_reclassifies_project_before_generation(client, monkeypatch, tmp_path):
    from src.api.routers import chat as chat_router

    generated_types = []
    deployments = []

    async def fake_generate_project_artifact(db, project, prompt):
        generated_types.append(project.type)
        return tmp_path / "artifact"

    monkeypatch.setattr(chat_router, "ConversationService", _FakeConversationService)
    monkeypatch.setattr(
        chat_router, "generate_project_artifact_agentic", fake_generate_project_artifact
    )
    monkeypatch.setattr(chat_router, "commit_snapshot", lambda artifact_path, message: "abc123")
    monkeypatch.setattr(
        chat_router,
        "create_deployment_for_project",
        lambda db, project: deployments.append(project.id),
    )

    headers = auth_tokens(client, "reclassify@airuntime.dev")
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Flexible Project", "description": ""},
    ).json()
    assert project["type"] == "website"
    chat = client.post(f"/api/v1/projects/{project['id']}/chats", headers=headers).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/chats/{chat['id']}/stream",
        headers=headers,
        json={"content": "Make a Telegram bot for support requests"},
    )

    assert response.status_code == 200
    assert generated_types == ["telegram_bot"]
    assert deployments == []
    assert "TELEGRAM_BOT_TOKEN" in response.text
    updated = client.get(f"/api/v1/projects/{project['id']}", headers=headers).json()
    assert updated["type"] == "telegram_bot"
    assert updated["status"] == "needs_configuration"
