#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_DOMAIN="${APP_DOMAIN:-airuntime.ru}"
ADMIN_EMAIL="admin@${APP_DOMAIN}"
NOREPLY_EMAIL="noreply@${APP_DOMAIN}"

mkdir -p infra/mail/config/ssl infra/mail/data infra/mail/state

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi

ADMIN_PASS="${MAIL_ADMIN_PASSWORD:?MAIL_ADMIN_PASSWORD is required}"
NOREPLY_PASS="${MAIL_NOREPLY_PASSWORD:?MAIL_NOREPLY_PASSWORD is required}"

# docker-mailserver account format: user@domain|password
cat > infra/mail/config/postfix-accounts.cf <<EOF
${ADMIN_EMAIL}|$(doveadm pw -s SHA512-CRYPT -p "${ADMIN_PASS}" 2>/dev/null || openssl passwd -6 "${ADMIN_PASS}")
${NOREPLY_EMAIL}|$(doveadm pw -s SHA512-CRYPT -p "${NOREPLY_PASS}" 2>/dev/null || openssl passwd -6 "${NOREPLY_PASS}")
EOF

touch infra/mail/config/postfix-virtual.cf

if [[ ! -f infra/mail/config/ssl/cert.pem ]]; then
  openssl req -x509 -newkey rsa:4096 -sha256 -days 825 -nodes \
    -keyout infra/mail/config/ssl/key.pem \
    -out infra/mail/config/ssl/cert.pem \
    -subj "/CN=mail.${APP_DOMAIN}" \
    -addext "subjectAltName=DNS:mail.${APP_DOMAIN},DNS:${APP_DOMAIN}"
fi

echo "Mail accounts configured for ${ADMIN_EMAIL} and ${NOREPLY_EMAIL}"
