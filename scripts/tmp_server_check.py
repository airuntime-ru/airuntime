import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

host = os.environ["AIRUNTIME_SSH_HOST"]
username = os.environ.get("AIRUNTIME_SSH_USER", "root")
password = os.environ["AIRUNTIME_SSH_PASSWORD"]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=username, password=password, timeout=30)

cmds = [
    "cd /home/airuntime && ls -la docker-compose*.yml 2>/dev/null; git log -1 --oneline; git status --short | head -20",
    "docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | sort",
    "cd /home/airuntime && docker compose -f docker-compose.prod.yml --env-file .env config --services 2>&1",
    "cd /home/airuntime && docker compose -f docker-compose.yml --env-file .env config --services 2>&1",
    "systemctl cat airuntime.service 2>/dev/null | head -25",
]

for cmd in cmds:
    print("=" * 60)
    print(">>>", cmd[:100])
    _, o, e = ssh.exec_command(cmd, timeout=120)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print("ERR:", err)
ssh.close()
