from src.core.config import settings
from src.services import cloudflare_dns


def test_sync_dns_skipped_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "cf_zone_id", None)
    monkeypatch.setattr(settings, "cf_api_token", None)
    monkeypatch.setattr(settings, "server_ip", None)

    host = cloudflare_dns.sync_dns_for_website_deploy("demo")

    assert host is None


def test_ensure_platform_dns_upserts_records(monkeypatch):
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(method: str, path: str, body: dict | None = None):
        calls.append((method, path, body))
        if method == "GET":
            return {"success": True, "result": []}
        return {"success": True, "result": {}}

    monkeypatch.setattr(settings, "cf_zone_id", "zone-1")
    monkeypatch.setattr(settings, "cf_api_token", "token-1")
    monkeypatch.setattr(settings, "server_ip", "203.0.113.10")
    monkeypatch.setattr(settings, "app_domain", "airuntime.ru")
    monkeypatch.setattr(settings, "public_base_domain", None)
    monkeypatch.setattr(cloudflare_dns, "_request", fake_request)

    messages = cloudflare_dns.ensure_platform_dns()

    assert any("*.airuntime.ru" in message for message in messages)
    assert any(call[0] == "POST" and call[2]["name"] == "*.airuntime.ru" for call in calls)


def test_sync_dns_for_website_deploy_returns_host_only(monkeypatch):
    monkeypatch.setattr(settings, "cf_zone_id", "zone-1")
    monkeypatch.setattr(settings, "cf_api_token", "token-1")
    monkeypatch.setattr(settings, "server_ip", "203.0.113.10")
    monkeypatch.setattr(settings, "app_domain", "airuntime.ru")
    monkeypatch.setattr(settings, "public_base_domain", None)
    monkeypatch.setattr(
        cloudflare_dns,
        "ensure_platform_dns",
        lambda: ["updated A airuntime.ru", "updated A www.airuntime.ru"],
    )
    monkeypatch.setattr(
        cloudflare_dns, "upsert_dns_record", lambda *a, **k: "created A demo.airuntime.ru"
    )

    host = cloudflare_dns.sync_dns_for_website_deploy("demo")

    assert host == "demo.airuntime.ru"


def test_user_facing_dns_note_is_short_russian():
    note = cloudflare_dns.user_facing_dns_note("demo", host="demo.airuntime.ru")
    assert note == "Поддомен `demo.airuntime.ru` настроен в Cloudflare"
    assert "www" not in note
    assert "updated A" not in note

    err = cloudflare_dns.user_facing_dns_note("demo", error="token expired")
    assert "Не удалось настроить поддомен" in err
    assert "token expired" in err
