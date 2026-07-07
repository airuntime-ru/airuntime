"""Cloudflare DNS sync for platform and project deployments."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


class CloudflareDnsError(RuntimeError):
    pass


def dns_configured() -> bool:
    return bool(settings.cf_zone_id and settings.cf_api_token and settings.server_ip)


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    if not settings.cf_zone_id or not settings.cf_api_token:
        raise CloudflareDnsError("Cloudflare credentials are not configured")

    url = f"https://api.cloudflare.com/client/v4/zones/{settings.cf_zone_id}{path}"
    headers = {
        "Authorization": f"Bearer {settings.cf_api_token}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.request(method, url, headers=headers, json=body)
    payload = response.json()
    if response.status_code >= 400 or not payload.get("success", False):
        errors = payload.get("errors") or response.text
        raise CloudflareDnsError(f"Cloudflare API error: {errors}")
    return payload


def upsert_dns_record(
    record_type: str,
    name: str,
    content: str,
    *,
    priority: int | None = None,
) -> str:
    existing = _request("GET", f"/dns_records?type={record_type}&name={name}")
    records = existing.get("result") or []
    body: dict[str, Any] = {
        "type": record_type,
        "name": name,
        "content": content,
        "proxied": False,
        "ttl": 1,
    }
    if priority is not None:
        body["priority"] = priority

    if records:
        record_id = records[0]["id"]
        _request("PUT", f"/dns_records/{record_id}", body)
        return f"updated {record_type} {name}"

    _request("POST", "/dns_records", body)
    return f"created {record_type} {name}"


def ensure_platform_dns() -> list[str]:
    """Apply the same records as scripts/setup_cloudflare_dns.sh."""
    if not dns_configured():
        raise CloudflareDnsError("SERVER_IP, CF_ZONE_ID and CF_API_TOKEN are required")

    domain = settings.resolved_app_domain
    ip = settings.server_ip
    if not ip:
        raise CloudflareDnsError("SERVER_IP is required")

    messages: list[str] = []
    for host in [
        domain,
        f"www.{domain}",
        f"api.{domain}",
        f"admin.{domain}",
        f"s3.{domain}",
        f"s3-console.{domain}",
        f"mail.{domain}",
        f"*.{domain}",
    ]:
        messages.append(upsert_dns_record("A", host, ip))

    messages.append(upsert_dns_record("MX", domain, f"mail.{domain}", priority=10))
    messages.append(upsert_dns_record("TXT", domain, f"v=spf1 mx a ip4:{ip} -all"))
    messages.append(
        upsert_dns_record(
            "TXT",
            f"_dmarc.{domain}",
            f"v=DMARC1; p=quarantine; rua=mailto:admin@{domain}",
        )
    )
    return messages


def sync_dns_for_website_deploy(subdomain: str) -> list[str]:
    """Sync Cloudflare DNS when a website is deployed."""
    if not dns_configured():
        logger.info("Cloudflare DNS sync skipped: credentials not configured")
        return ["dns sync skipped (not configured)"]

    messages = ensure_platform_dns()
    logger.info("Cloudflare DNS synced for %s.%s", subdomain, settings.resolved_app_domain)
    return messages
