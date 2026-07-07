# AIRuntime Production Checklist

## Verified in repository

- [x] AIRuntime branding across frontend, backend OpenAPI, Docker compose
- [x] Config-driven domains (`APP_DOMAIN`, `FRONTEND_URL`, `API_URL`)
- [x] Auth: register, login, refresh rotation, logout, purpose tokens for verify/reset
- [x] Optional SMTP email delivery for verify/reset flows
- [x] Projects CRUD (create, list, get, patch)
- [x] Project workspace tabs: Overview, Chat, Deployments, Logs, Secrets, Settings, History
- [x] Chat: create, list, messages, POST SSE stream, prompt guard, credits gate
- [x] Real Docker deployment via Engine API (worker + socket mount)
- [x] Secrets encryption + delete endpoint
- [x] Provider config endpoint (authenticated)
- [x] Security middleware (CORS, trusted hosts, headers, rate limiting)
- [x] Alembic migrations, Docker Compose, smoke test, pytest, GitHub Actions CI
- [x] Chat file uploads via MinIO (S3-compatible object storage)

## Required before public launch at production domain

- [ ] Set `ENVIRONMENT=production`, strong `JWT_SECRET_KEY`, `APP_ENCRYPTION_KEY`
- [ ] Configure `APP_DOMAIN`, `FRONTEND_URL`, `API_URL`, `ALLOWED_ORIGINS`, `ALLOWED_HOSTS`
- [ ] Configure `S3_*` / MinIO credentials and public endpoint for production file downloads
- [ ] Configure TLS termination — see `deployment/reverse_proxy.example.yml`
- [ ] Managed PostgreSQL + Redis with backups and monitoring
- [ ] Run `docker compose up --build` and `python scripts/smoke_test.py` on staging

## Known limitations

- Normalized `logs`, `git_commits`, `ai_providers` tables deferred (inline project fields used)
- RBAC roles stored but not enforced beyond ownership checks
