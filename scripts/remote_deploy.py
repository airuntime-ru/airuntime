#!/usr/bin/env python3
"""Run production deployment on the server via SSH."""

from __future__ import annotations

import secrets
import string
import sys

import paramiko

HOST = "155.212.228.202"
USER = "root"
PASS = "evBZ&rtczu85"
REPO = "/home/airuntime"
DOMAIN = "airuntime.ru"
ZONE_ID = "69f9a9689e8eb5bba417737c8c44a9d9"
CF_TOKEN = os.environ.get("CF_API_TOKEN", "")


def rand(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> int:
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
            print("ERR:", err[-5000:].encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
        print("exit", code)
        return code, out, err

    secrets_map = {
        "APP_DOMAIN": DOMAIN,
        "POSTGRES_DB": "airuntime",
        "POSTGRES_USER": "airuntime",
        "POSTGRES_PASSWORD": rand(32),
        "JWT_SECRET_KEY": rand(48),
        "APP_ENCRYPTION_KEY": rand(32),
        "DJANGO_SECRET_KEY": rand(48),
        "DJANGO_SUPERUSER_PASSWORD": "admin123",
        "S3_ACCESS_KEY": "airuntime",
        "S3_SECRET_KEY": rand(32),
        "S3_BUCKET": "airuntime-files",
        "MAIL_ADMIN_PASSWORD": rand(20),
        "MAIL_NOREPLY_PASSWORD": rand(20),
        "PROVIDER_NAME": "openai",
        "OPENAI_API_KEY": "",
    }

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

    env_lines = "\n".join(f"{k}={v}" for k, v in secrets_map.items())
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

    accounts = (
        f"admin@{DOMAIN}|{{PLAIN}}{secrets_map['MAIL_ADMIN_PASSWORD']}\n"
        f"noreply@{DOMAIN}|{{PLAIN}}{secrets_map['MAIL_NOREPLY_PASSWORD']}\n"
    )
    with ssh.open_sftp().file(f"{REPO}/infra/mail/config/postfix-accounts.cf", "w") as fh:
        fh.write(accounts)
    run(f"touch {REPO}/infra/mail/config/postfix-virtual.cf")

    dns_script = f"""
python3 - <<'PY'
import json, urllib.request, urllib.error
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

for host in [DOMAIN, f"www.{{DOMAIN}}", f"api.{{DOMAIN}}", f"admin.{{DOMAIN}}", f"s3.{{DOMAIN}}", f"s3-console.{{DOMAIN}}", f"mail.{{DOMAIN}}"]:
    upsert("A", host, IP)
upsert("MX", DOMAIN, f"mail.{{DOMAIN}}", 10)
upsert("TXT", DOMAIN, f"v=spf1 mx a ip4:{{IP}} -all")
upsert("TXT", f"_dmarc.{{DOMAIN}}", f"v=DMARC1; p=quarantine; rua=mailto:admin@{{DOMAIN}}")
PY
"""
    run(dns_script)

    run(f"cd {REPO} && docker compose -f docker-compose.prod.yml --env-file .env up -d --build", timeout=3600)
    run(
        f"cp {REPO}/infra/systemd/airuntime.service /etc/systemd/system/airuntime.service && "
        "systemctl daemon-reload && systemctl enable airuntime.service"
    )

    admin_pass = secrets_map["MAIL_ADMIN_PASSWORD"]
    noreply_pass = secrets_map["MAIL_NOREPLY_PASSWORD"]
    run(
        f"cd {REPO} && docker compose -f docker-compose.prod.yml exec -T mailserver "
        f"setup email add admin@{DOMAIN} {admin_pass} || true"
    )
    run(
        f"cd {REPO} && docker compose -f docker-compose.prod.yml exec -T mailserver "
        f"setup email add noreply@{DOMAIN} {noreply_pass} || true"
    )

    run(f"cd {REPO} && docker compose -f docker-compose.prod.yml ps")
    run("sleep 15 && curl -skI https://api.airuntime.ru/api/v1/health || true")
    run("curl -skI https://admin.airuntime.ru/ || true")
    run("curl -skI https://airuntime.ru/ || true")
    run("curl -skI https://s3.airuntime.ru/minio/health/live || true")

    ssh.close()
    print("MAIL_ADMIN_PASSWORD", admin_pass)
    print("MAIL_NOREPLY_PASSWORD", noreply_pass)
    return 0


if __name__ == "__main__":
    sys.exit(main())
