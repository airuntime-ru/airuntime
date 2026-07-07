"""Basic smoke test for auth -> projects -> chat stream flow.

Usage:
  python scripts/smoke_test.py
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "http://localhost:8000/api/v1"


def request_json(path: str, method: str = "GET", data: dict | None = None, token: str | None = None) -> dict:
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(f"{BASE_URL}{path}", data=payload, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def run() -> None:
    email = "smoke@airuntime.dev"
    password = "smoke12345"
    try:
        auth = request_json("/auth/register", method="POST", data={"email": email, "password": password})
    except urllib.error.HTTPError:
        auth = request_json("/auth/login", method="POST", data={"email": email, "password": password})

    token = auth["access_token"]
    project = request_json(
        "/projects",
        method="POST",
        data={"type": "website", "name": "Smoke Project", "description": "Smoke test"},
        token=token,
    )
    chat = request_json(f"/projects/{project['id']}/chats", method="POST", token=token)
    request_json(
        f"/projects/{project['id']}/chats/{chat['id']}/messages",
        method="POST",
        data={"content": "Build hello world website"},
        token=token,
    )

    req = urllib.request.Request(
        f"{BASE_URL}/projects/{project['id']}/chats/{chat['id']}/stream",
        data=json.dumps({"content": "Build hello world website"}).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as response:
        body = response.read().decode("utf-8")
        if "[DONE]" not in body:
            raise RuntimeError("Stream did not complete")
    print("Smoke test passed.")


if __name__ == "__main__":
    run()
