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
| `plan_request_created` / `plan_request_approved` / `plan_request_rejected` | plan change requests |

Shared macros live in `templates/macros.html.j2` (button, OTP, badges, billing summary, project link).

## Design

Same visual language as the landing and the cabinet: a deep-space masthead (`#070C17`), a
brand-gradient hairline, then a white reading card. Palette and type stacks are globals in
`render.py`, so the whole system moves from one place.

Two rules the templates must keep:

- **Every gradient ships with a solid `bgcolor` twin.** Outlook renders with Word, which drops
  `background-image` — without the twin, a gradient area comes out white.
- **`color-scheme: light only` plus explicit dark-mode guards.** The `@media (prefers-color-scheme: dark)`
  block in `base.html.j2` pins the masthead dark and the card light so a client forcing dark
  mode cannot muddy either one.

`billing_summary` rows take an optional `block: True` for free text (an error summary, a
rejection note): the row stacks and goes left-aligned instead of right-aligning a sentence.

## Logo

- Public asset: `frontend/public/brand/email-logo.png` → `{FRONTEND_URL}/brand/email-logo.png`
- Send path embeds the same PNG as CID `airuntime-logo` for clients that block remote images
- Backend copy: `backend/src/assets/brand/email-logo.png` (keep the two byte-identical)
- Light-ink wordmark (Inter) plus the gradient mark, exported at 3x on transparency and shown at
  166×40. It sits directly on the masthead — a client that drops the alpha channel composites to
  black, which the masthead already is.

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
