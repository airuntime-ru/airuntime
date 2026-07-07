#!/usr/bin/env python3
"""Server bootstrap for AIRuntime production deployment."""

from __future__ import annotations

import json
import os
import secrets
import string
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request


SERVER_IP = os.environ.get("SERVER_IP", "155.212.228.202")
APP_DOMAIN = os.environ.get("APP_DOMAIN", "airuntime.ru")
ZONE_ID = os.environ.get("CF_ZONE_ID", "")
CF_TOKEN = os.environ.get("CF_API_TOKEN", "")
REPO_DIR = "/home/airuntime"


def run(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    print(f"$ {cmd}")
    return subprocess.run(cmd, shell=True, check=check, text=True)


def rand_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def cf_request(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {CF_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def upsert_dns(record_type: str, name: str, content: str, priority: int | None = None) -> None:
    existing = cf_request("GET", f"/dns_records?type={record_type}&name={name}")
    body = {
        "type": record_type,
        "name": name,
        "content": content,
        "proxied": False,
        "ttl": 1,
    }
    if priority is not None:
        body["priority"] = priority
    if existing.get("result"):
        record_id = existing["result"][0]["id"]
        cf_request("PUT", f"/dns_records/{record_id}", body)
        print(f"Updated {record_type} {name}")
    else:
        cf_request("POST", "/dns_records", body)
        print(f"Created {record_type} {name}")


def configure_dns() -> None:
    try:
        upsert_dns("A", APP_DOMAIN, SERVER_IP)
        upsert_dns("A", f"www.{APP_DOMAIN}", SERVER_IP)
        upsert_dns("A", f"api.{APP_DOMAIN}", SERVER_IP)
        upsert_dns("A", f"admin.{APP_DOMAIN}", SERVER_IP)
        upsert_dns("A", f"s3.{APP_DOMAIN}", SERVER_IP)
        upsert_dns("A", f"s3-console.{APP_DOMAIN}", SERVER_IP)
        upsert_dns("A", f"mail.{APP_DOMAIN}", SERVER_IP)
        upsert_dns("MX", APP_DOMAIN, f"mail.{APP_DOMAIN}", priority=10)
        upsert_dns("TXT", APP_DOMAIN, f"v=spf1 mx a ip4:{SERVER_IP} -all")
        upsert_dns("TXT", f"_dmarc.{APP_DOMAIN}", f"v=DMARC1; p=quarantine; rua=mailto:admin@{APP_DOMAIN}")
        print("Cloudflare DNS configured")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        print(f"Cloudflare DNS setup failed ({exc.code}): {body}", file=sys.stderr)


def write_env(secrets_map: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in secrets_map.items()]
    env_path = os.path.join(REPO_DIR, ".env")
    with open(env_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(env_path, 0o600)
    print(f"Wrote {env_path}")


def setup_mail_accounts(admin_pass: str, noreply_pass: str) -> None:
    config_dir = os.path.join(REPO_DIR, "infra/mail/config")
    ssl_dir = os.path.join(config_dir, "ssl")
    os.makedirs(ssl_dir, exist_ok=True)
    os.makedirs(os.path.join(REPO_DIR, "infra/mail/data"), exist_ok=True)
    os.makedirs(os.path.join(REPO_DIR, "infra/mail/state"), exist_ok=True)

    cert = os.path.join(ssl_dir, "cert.pem")
    key = os.path.join(ssl_dir, "key.pem")
    if not os.path.exists(cert):
        run(
            f"openssl req -x509 -newkey rsa:4096 -sha256 -days 825 -nodes "
            f"-keyout {key} -out {cert} "
            f"-subj '/CN=mail.{APP_DOMAIN}' "
            f"-addext 'subjectAltName=DNS:mail.{APP_DOMAIN},DNS:{APP_DOMAIN}'"
        )

    accounts_path = os.path.join(config_dir, "postfix-accounts.cf")
    virtual_path = os.path.join(config_dir, "postfix-virtual.cf")
    open(virtual_path, "a", encoding="utf-8").close()

    # Placeholder accounts; hashes are finalized after mailserver starts.
    with open(accounts_path, "w", encoding="utf-8") as fh:
        fh.write(
            textwrap.dedent(
                f"""
                admin@{APP_DOMAIN}|{{PLAIN}}{admin_pass}
                noreply@{APP_DOMAIN}|{{PLAIN}}{noreply_pass}
                """
            ).strip()
            + "\n"
        )
    print("Mail account placeholders written")


def main() -> None:
    os.chdir(REPO_DIR)

    if subprocess.run("command -v docker", shell=True).returncode != 0:
        run("apt-get update")
        run("apt-get install -y ca-certificates curl gnupg jq openssl git")
        run(
            "install -m 0755 -d /etc/apt/keyrings && "
            "curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc && "
            "chmod a+r /etc/apt/keyrings/docker.asc"
        )
        run(
            'bash -c \'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] '
            "https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo ${VERSION_CODENAME}) stable\" "
            "> /etc/apt/sources.list.d/docker.list'"
        )
        run("apt-get update")
        run("apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin")
        run("systemctl enable --now docker")

    run("git pull origin main")

    postgres_pass = rand_password()
    jwt_secret = rand_password(48)
    encryption_key = rand_password(32)
    django_secret = rand_password(48)
    s3_secret = rand_password(32)
    mail_admin_pass = rand_password(20)
    mail_noreply_pass = rand_password(20)

    write_env(
        {
            "APP_DOMAIN": APP_DOMAIN,
            "POSTGRES_DB": "airuntime",
            "POSTGRES_USER": "airuntime",
            "POSTGRES_PASSWORD": postgres_pass,
            "JWT_SECRET_KEY": jwt_secret,
            "APP_ENCRYPTION_KEY": encryption_key,
            "DJANGO_SECRET_KEY": django_secret,
            "DJANGO_SUPERUSER_PASSWORD": "admin123",
            "S3_ACCESS_KEY": "airuntime",
            "S3_SECRET_KEY": s3_secret,
            "S3_BUCKET": "airuntime-files",
            "MAIL_ADMIN_PASSWORD": mail_admin_pass,
            "MAIL_NOREPLY_PASSWORD": mail_noreply_pass,
            "PROVIDER_NAME": "openai",
            "OPENAI_API_KEY": "",
        }
    )

    configure_dns()
    setup_mail_accounts(mail_admin_pass, mail_noreply_pass)

    run("docker compose -f docker-compose.prod.yml --env-file .env up -d --build", check=False)

    run("cp infra/systemd/airuntime.service /etc/systemd/system/airuntime.service")
    run("systemctl daemon-reload")
    run("systemctl enable airuntime.service")

    print("Deployment bootstrap finished")
    print(f"Mail admin@{APP_DOMAIN} password: {mail_admin_pass}")
    print(f"Mail noreply@{APP_DOMAIN} password: {mail_noreply_pass}")


if __name__ == "__main__":
    main()
