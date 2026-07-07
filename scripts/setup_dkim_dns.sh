#!/usr/bin/env bash
# Sync DKIM TXT record from running mailserver to Cloudflare.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_DOMAIN="${APP_DOMAIN:-airuntime.ru}"
CF_ZONE_ID="${CF_ZONE_ID:?CF_ZONE_ID is required}"
CF_API_TOKEN="${CF_API_TOKEN:?CF_API_TOKEN is required}"
DKIM_NAME="mail._domainkey.${APP_DOMAIN}"

raw="$(docker compose -f docker-compose.prod.yml exec -T mailserver cat "/tmp/docker-mailserver/opendkim/keys/${APP_DOMAIN}/mail.txt")"
content="$(python3 - <<'PY' "$raw"
import re, sys
raw = sys.argv[1]
chunks = []
for line in raw.splitlines():
    line = line.strip().strip('"')
    if not line or line.startswith("mail._domainkey") or "DKIM key" in line:
        continue
    line = line.strip("()")
    chunks.append(line)
value = re.sub(r"\s+", "", "".join(chunks))
print(value)
PY
)"

existing="$(curl -sS -X GET "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records?type=TXT&name=${DKIM_NAME}" \
  -H "Authorization: Bearer ${CF_API_TOKEN}" \
  -H "Content-Type: application/json")"
record_id="$(python3 - <<'PY' "$existing"
import json, sys
data = json.load(sys.stdin)
print(data["result"][0]["id"] if data.get("result") else "")
PY
)"

payload="$(python3 - <<'PY' "$DKIM_NAME" "$content"
import json, sys
print(json.dumps({
    "type": "TXT",
    "name": sys.argv[1],
    "content": sys.argv[2],
    "proxied": False,
    "ttl": 1,
}))
PY
)"

if [[ -n "$record_id" ]]; then
  curl -sS -X PUT "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records/${record_id}" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" \
    -H "Content-Type: application/json" \
    --data "$payload" >/dev/null
  echo "Updated DKIM TXT ${DKIM_NAME}"
else
  curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" \
    -H "Content-Type: application/json" \
    --data "$payload" >/dev/null
  echo "Created DKIM TXT ${DKIM_NAME}"
fi
