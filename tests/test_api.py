from tests.conftest import auth_tokens


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

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
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

    listed = client.get(f"/api/v1/projects/{project['id']}/chats/{chat['id']}/files", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
