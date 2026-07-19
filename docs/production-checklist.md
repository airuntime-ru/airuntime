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
- [ ] Codex per-project isolation (see `codex_worker.py`): after first `docker compose up`,
      confirm `docker volume ls` actually has a volume named `generated_projects_volume_name`
      (default `airruntime_airruntime_projects_data` - differs if deployed with a non-default
      `COMPOSE_PROJECT_NAME`/`-p`). If it doesn't match, every Codex turn silently falls back to
      full shared-volume access (logged, not fatal) instead of the intended per-project mount -
      check `docker logs <worker container>` for the `[codex_worker] could not resolve
      per-project mount` warning to catch this before relying on the isolation.
- [ ] Optional hardening: set `CODEX_DOCKER_HOST=tcp://docker-socket-proxy:2375` once the
      `docker-socket-proxy` compose service is confirmed reachable, to stop handing the per-turn
      Codex container the raw host socket. Not a full per-project container ACL by itself (the
      proxy narrows which Docker API *categories* are allowed, not "only this project's
      containers") - see the isolation section in `docs/architecture.md`.

## Known limitations

- Normalized `logs`, `git_commits`, `ai_providers` tables deferred (inline project fields used)
- RBAC roles stored but not enforced beyond ownership checks
- Codex's per-turn container still shares the Docker daemon (raw or via socket-proxy) with every
  other project's containers - filesystem access is scoped per-project, but a Codex turn could
  still, in principle, name-guess and touch another project's *container* through that daemon.
  True per-project container ACLs (or moving off a shared daemon entirely - gVisor/microVM) is
  tracked as follow-up, not done here.
