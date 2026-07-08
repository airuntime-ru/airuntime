import json

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


def test_stream_prompt_generates_artifact_and_queues_deployment(
    client, monkeypatch, tmp_path
):
    from src.api.routers import chat as chat_router

    generated = []
    deployments = []

    def fake_generate_project_artifact(db, project, prompt):
        generated.append((project.id, prompt))
        return tmp_path / "artifact"

    def fake_create_deployment(db, project):
        deployments.append(project.id)
        return None

    monkeypatch.setattr(chat_router, "ConversationService", _FakeConversationService)
    monkeypatch.setattr(chat_router, "generate_project_artifact", fake_generate_project_artifact)
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
    chunks = [
        json.loads(line.removeprefix("data: "))["chunk"]
        for line in response.text.splitlines()
        if line.startswith("data: {")
    ]
    assert any("Сайт собран и поставлен в очередь на запуск" in chunk for chunk in chunks)
    assert "data: [DONE]" in response.text
    assert generated
    assert deployments == [generated[0][0]]

    updated = client.get(f"/api/v1/projects/{project['id']}", headers=headers).json()
    assert updated["status"] == "ready"


def test_stream_subdomain_from_prompt_sets_deploy_subdomain(client, monkeypatch, tmp_path):
    from src.api.routers import chat as chat_router

    deployments: list[str | None] = []

    def fake_generate_project_artifact(db, project, prompt):
        return tmp_path / "artifact"

    def fake_create_deployment(db, project):
        deployments.append(project.deploy_subdomain)
        return None

    monkeypatch.setattr(chat_router, "ConversationService", _FakeConversationService)
    monkeypatch.setattr(chat_router, "generate_project_artifact", fake_generate_project_artifact)
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
