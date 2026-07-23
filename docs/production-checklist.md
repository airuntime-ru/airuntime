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
      (default `airuntime_airruntime_projects_data` - differs if deployed with a non-default
      `COMPOSE_PROJECT_NAME`/`-p`). The default previously had an extra "r"
      (`airr`untime`_airr`untime...) and never matched Compose's real
      `<project-name>_<volume-key>` name on either dev or prod, so every Codex turn was silently
      falling back - fixed 2026-07-23, but if this drifts again: the fallback now mounts the
      volume by name (correct data, just unscoped to one project) rather than the old broken
      behavior of bind-mounting a container-internal path as if it were a host path, which
      silently ran turns against an empty throwaway directory - the agent would report files
      written/tests run with no error anywhere, and none of it would reach the real project.
      Check `docker logs <worker container>` for the `could not resolve per-project mount`
      warning to catch a mismatch before relying on per-project isolation.
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
