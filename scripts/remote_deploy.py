#!/usr/bin/env python3
"""Run production deployment on the server via SSH.

Usage:
  export DEPLOY_SSH_HOST=155.212.228.202
  export DEPLOY_SSH_USER=root
  export DEPLOY_SSH_PASSWORD=...
  export CF_API_TOKEN=...
  python scripts/remote_deploy.py
"""

from __future__ import annotations

import os
import secrets
import string
import sys

import paramiko

HOST = os.environ.get("DEPLOY_SSH_HOST", "")
USER = os.environ.get("DEPLOY_SSH_USER", "root")
PASS = os.environ.get("DEPLOY_SSH_PASSWORD", "")
REPO = os.environ.get("DEPLOY_REPO_DIR", "/home/airuntime")
DOMAIN = os.environ.get("APP_DOMAIN", "airuntime.ru")
ZONE_ID = os.environ.get("CF_ZONE_ID", "")
CF_TOKEN = os.environ.get("CF_API_TOKEN", "")


def rand(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> int:
    if not HOST or not PASS:
        print("DEPLOY_SSH_HOST and DEPLOY_SSH_PASSWORD are required", file=sys.stderr)
        return 1

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=30)

    def run(cmd: str, timeout: int = 1800) -> tuple[int, str, str]:
        print(">>>", cmd[:200])
        _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode()
        err = stderr.read().decode()
        code = stdout.channel.recv_exit_status()
        if out:
            print(out[-10000:].encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
        if err:
            print(
                "ERR:",
                err[-5000:].encode("utf-8", errors="replace").decode("utf-8", errors="replace"),
            )
        print("exit", code)
        return code, out, err

    install_docker = r"""
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg jq openssl git
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
fi
"""
    run(install_docker, timeout=1200)
    run(f"cd {REPO} && git pull origin main")

    env_lines = "\n".join(
        f"{k}={v}"
        for k, v in {
            "APP_DOMAIN": DOMAIN,
            "POSTGRES_DB": "airuntime",
            "POSTGRES_USER": "airuntime",
            "POSTGRES_PASSWORD": rand(32),
            "JWT_SECRET_KEY": rand(48),
            "APP_ENCRYPTION_KEY": rand(32),
            "DJANGO_SECRET_KEY": rand(48),
            "DJANGO_SUPERUSER_PASSWORD": os.environ.get("DJANGO_SUPERUSER_PASSWORD", "admin123"),
            "S3_ACCESS_KEY": "airuntime",
            "S3_SECRET_KEY": rand(32),
            "S3_BUCKET": "airuntime-files",
            "MAIL_ADMIN_PASSWORD": rand(20),
            "MAIL_NOREPLY_PASSWORD": rand(20),
            "PROVIDER_NAME": "openai",
            "OPENAI_API_KEY": "",
        }.items()
    )

    _, out, _ = run(f"test -f {REPO}/.env && echo exists || echo missing")
    if "missing" in out:
        sftp = ssh.open_sftp()
        with sftp.file(f"{REPO}/.env", "w") as remote_env:
            remote_env.write(env_lines + "\n")
        sftp.chmod(f"{REPO}/.env", 0o600)
        sftp.close()

    run(
        f"mkdir -p {REPO}/infra/mail/config/ssl {REPO}/infra/mail/data {REPO}/infra/mail/state && "
        f"test -f {REPO}/infra/mail/config/ssl/cert.pem || "
        f"openssl req -x509 -newkey rsa:4096 -sha256 -days 825 -nodes "
        f"-keyout {REPO}/infra/mail/config/ssl/key.pem "
        f"-out {REPO}/infra/mail/config/ssl/cert.pem "
        f"-subj '/CN=mail.{DOMAIN}' "
        f"-addext 'subjectAltName=DNS:mail.{DOMAIN},DNS:{DOMAIN}'"
    )

    if CF_TOKEN and ZONE_ID:
        dns_script = f"""
python3 - <<'PY'
import json, urllib.request
ZONE = "{ZONE_ID}"
TOKEN = "{CF_TOKEN}"
IP = "{HOST}"
DOMAIN = "{DOMAIN}"

def req(method, path, body=None):
    url = f"https://api.cloudflare.com/client/v4/zones/{{ZONE}}{{path}}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={{"Authorization": f"Bearer {{TOKEN}}", "Content-Type": "application/json"}},
    )
    with urllib.request.urlopen(request) as resp:
        return json.load(resp)

def upsert(record_type, name, content, priority=None):
    existing = req("GET", f"/dns_records?type={{record_type}}&name={{name}}")
    body = {{"type": record_type, "name": name, "content": content, "proxied": False, "ttl": 1}}
    if priority is not None:
        body["priority"] = priority
    if existing.get("result"):
        req("PUT", f"/dns_records/{{existing['result'][0]['id']}}", body)
    else:
        req("POST", "/dns_records", body)
    print("ok", record_type, name)

for host in [DOMAIN, f"www.{{DOMAIN}}", f"api.{{DOMAIN}}", f"admin.{{DOMAIN}}", f"s3.{{DOMAIN}}", f"s3-console.{{DOMAIN}}", f"mail.{{DOMAIN}}", f"*.{DOMAIN}"]:
    upsert("A", host, IP)
upsert("MX", DOMAIN, f"mail.{{DOMAIN}}", 10)
upsert("TXT", DOMAIN, f"v=spf1 mx a ip4:{{IP}} -all")
upsert("TXT", f"_dmarc.{{DOMAIN}}", f"v=DMARC1; p=quarantine; rua=mailto:admin@{{DOMAIN}}")
PY
"""
        run(dns_script)

    run(
        f"cd {REPO} && docker compose -f docker-compose.prod.yml --env-file .env up -d --build",
        timeout=3600,
    )
    run(
        f"cp {REPO}/infra/systemd/airuntime.service /etc/systemd/system/airuntime.service && "
        "systemctl daemon-reload && systemctl enable airuntime.service"
    )

    run(f"cd {REPO} && docker compose -f docker-compose.prod.yml ps")
    run("sleep 15 && curl -sk https://api.airuntime.ru/health || true")
    run("curl -skI https://admin.airuntime.ru/ || true")
    run("curl -skI https://airuntime.ru/ || true")

    ssh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
