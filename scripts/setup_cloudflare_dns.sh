#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_DOMAIN="${APP_DOMAIN:-airuntime.ru}"
SERVER_IP="${SERVER_IP:?SERVER_IP is required}"
CF_ZONE_ID="${CF_ZONE_ID:?CF_ZONE_ID is required}"
CF_API_TOKEN="${CF_API_TOKEN:?CF_API_TOKEN is required}"

api() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  if [[ -n "$data" ]]; then
    curl -sS -X "$method" "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}${path}" \
      -H "Authorization: Bearer ${CF_API_TOKEN}" \
      -H "Content-Type: application/json" \
      --data "$data"
  else
    curl -sS -X "$method" "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}${path}" \
      -H "Authorization: Bearer ${CF_API_TOKEN}" \
      -H "Content-Type: application/json"
  fi
}

upsert_dns() {
  local type="$1"
  local name="$2"
  local content="$3"
  local priority="${4:-}"
  local existing
  existing=$(api GET "/dns_records?type=${type}&name=${name}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'] if d.get('result') else '')")

  local payload
  if [[ "$type" == "MX" ]]; then
    payload=$(jq -n --arg type "$type" --arg name "$name" --arg content "$content" --argjson priority "${priority:-10}" '{type:$type,name:$name,content:$content,priority:$priority,proxied:false,ttl:1}')
  else
    payload=$(jq -n --arg type "$type" --arg name "$name" --arg content "$content" '{type:$type,name:$name,content:$content,proxied:false,ttl:1}')
  fi

  if [[ -n "$existing" ]]; then
    api PUT "/dns_records/${existing}" "$payload" >/dev/null
    echo "Updated ${type} ${name}"
  else
    api POST "/dns_records" "$payload" >/dev/null
    echo "Created ${type} ${name}"
  fi
}

upsert_dns A "${APP_DOMAIN}" "${SERVER_IP}"
upsert_dns A "www.${APP_DOMAIN}" "${SERVER_IP}"
upsert_dns A "api.${APP_DOMAIN}" "${SERVER_IP}"
upsert_dns A "admin.${APP_DOMAIN}" "${SERVER_IP}"
upsert_dns A "s3.${APP_DOMAIN}" "${SERVER_IP}"
upsert_dns A "s3-console.${APP_DOMAIN}" "${SERVER_IP}"
upsert_dns A "mail.${APP_DOMAIN}" "${SERVER_IP}"
upsert_dns A "*.${APP_DOMAIN}" "${SERVER_IP}"
upsert_dns MX "${APP_DOMAIN}" "mail.${APP_DOMAIN}" 10
upsert_dns TXT "${APP_DOMAIN}" "v=spf1 mx a ip4:${SERVER_IP} -all"
upsert_dns TXT "_dmarc.${APP_DOMAIN}" "v=DMARC1; p=quarantine; rua=mailto:admin@${APP_DOMAIN}"

echo "DNS records configured (proxied=false). Add DKIM after mailserver setup."
