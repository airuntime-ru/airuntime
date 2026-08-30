#!/usr/bin/env bash
# Deploy notifications for Telegram + ops-bot deploy grace (suppresses false 502 alerts).
set -euo pipefail

PHASE="${1:-}"
DETAIL="${2:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -z "$PHASE" ]]; then
  echo "usage: notify_deploy.sh {started|finished|failed} [detail]" >&2
  exit 1
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

BOT_TOKEN="${AIRUNTIME_TELEGRAM_BOT_TOKEN:-${TELEGRAM_BOT_TOKEN:-}}"
CHAT_ID="${AIRUNTIME_TELEGRAM_CHAT_ID:-${TELEGRAM_CHAT_ID:-}}"
TOPIC_CODE="${AIRUNTIME_TELEGRAM_TOPIC_CODE:-${TELEGRAM_TOPIC_CODE:-}}"
GRACE_MINUTES="${DEPLOY_HEALTH_GRACE_MINUTES:-15}"
POST_FINISH_GRACE_MIN="${DEPLOY_POST_FINISH_GRACE_MIN:-3}"

_ops_bot_volume() {
  docker volume ls -q | grep -E 'ops_bot_state$' | head -1 || true
}

set_deploy_grace() {
  local minutes="$1"
  local clear_health_alerts="${2:-0}"
  local vol
  vol="$(_ops_bot_volume)"
  if [[ -z "$vol" ]]; then
    echo "notify_deploy: ops_bot volume missing — skip grace"
    return 0
  fi
  docker run --rm \
    -e "GRACE_MIN=${minutes}" \
    -e "CLEAR_HEALTH=${clear_health_alerts}" \
    -v "${vol}:/var/lib/ops-bot" \
    python:3.12-slim \
    python -c 'import json, os
from pathlib import Path
from datetime import UTC, datetime, timedelta

p = Path("/var/lib/ops-bot/state.json")
data = {}
if p.exists():
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}

minutes = float(os.environ["GRACE_MIN"])
if minutes > 0:
    data["deploy_grace_until"] = (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()
else:
    data.pop("deploy_grace_until", None)

if os.environ.get("CLEAR_HEALTH") == "1":
    data.pop("last_health_alert_fp", None)
    data.pop("last_health_alert_at", None)

p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(data.get("deploy_grace_until", ""))'
  echo "notify_deploy: grace set (${minutes} min)"
}

send_telegram() {
  local text="$1"
  if [[ -z "$BOT_TOKEN" || -z "$CHAT_ID" ]]; then
    echo "notify_deploy: telegram not configured — skip message"
    return 0
  fi
  export CHAT_ID TOPIC_CODE
  local payload
  payload=$(TEXT="$text" python3 - <<'PY'
import json
import os

text = os.environ["TEXT"]
topic = os.environ.get("TOPIC_CODE", "").strip()
body = {
    "chat_id": os.environ["CHAT_ID"],
    "text": text,
    "parse_mode": "HTML",
    "disable_web_page_preview": True,
}
if topic:
    body["message_thread_id"] = int(topic)
print(json.dumps(body))
PY
  )
  curl -fsS -X POST \
    "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null
  echo "notify_deploy: sent ($PHASE)"
}

case "$PHASE" in
  started)
    set_deploy_grace "$GRACE_MINUTES" 0
    send_telegram "<b>🚀 Релиз AIRuntime начался</b>
Приложение может быть временно недоступно.
<code>${DETAIL:-deploy}</code>"
    ;;
  finished)
    set_deploy_grace "$POST_FINISH_GRACE_MIN" 1
    send_telegram "<b>✅ Релиз AIRuntime завершён</b>
Приложение снова должно быть доступно.
<code>${DETAIL:-deploy.sh exit 0}</code>"
    ;;
  failed)
    set_deploy_grace 0 0
    send_telegram "<b>❌ Релиз AIRuntime упал</b>
<code>${DETAIL:-deploy.sh failed}</code>"
    ;;
  *)
    echo "unknown phase: $PHASE" >&2
    exit 1
    ;;
esac
