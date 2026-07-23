# Transactional email

AIRuntime sends branded multipart (text + HTML) mail via SMTP.

## Templates

Jinja2 package: `backend/src/services/email_templates/`

| Id | Trigger |
|---|---|
| `login_code` | `POST /auth/request-code` |
| `verify_email` | registration |
| `password_reset` | `POST /auth/forgot-password` |
| `low_credits` / `credits_exhausted` | billing worker sweep |
| `period_ending` / `period_renewed` | billing worker sweep |
| `invoice_created` | top-up request |
| `invoice_paid` | paid top-up credited |
| `project_deployed` / `deploy_failed` | deployment worker |

Shared macros live in `templates/macros.html.j2` (button, OTP, badges, billing summary).

## Logo

- Public asset: `frontend/public/brand/email-logo.png` → `{FRONTEND_URL}/brand/email-logo.png`
- Send path embeds the same PNG as CID `airuntime-logo` for clients that block remote images
- Backend copy: `backend/src/assets/brand/email-logo.png`
- Opaque RGB wordmark on solid `#FFFFFF` (no transparency). Header uses a white logo plate plus `color-scheme: light only` so dark-mode clients are less likely to invert the brand mark into a floating stamp.

## Local preview (no SMTP)

```bash
export PYTHONPATH=backend   # PowerShell: $env:PYTHONPATH='backend'
python -m scripts.preview_emails --open
```

Output: `backend/.email-preview/` (gitignored).

## Deliverability notes

- From display name: `SMTP_FROM_NAME` (default `AIRuntime`)
- Optional `SMTP_REPLY_TO` / `SUPPORT_EMAIL`
- Multipart alternative, UTF-8, Message-ID, Date
- SPF / DKIM / DMARC are configured on the mail host (see `scripts/setup_dkim_dns.sh` and docker-mailserver). Do not assume they are valid until DNS is verified for the live domain.
