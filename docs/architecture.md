# AIRuntime MVP - Step 1 Architecture

## 1) Product Principles

- The user interacts only with AI chat and product UI.
- Infrastructure complexity (servers, SSL, domains, reverse proxy, deployment) is hidden.
- Premium, minimal, animation-rich UX (dark by default).
- Secure-by-design: secrets never exposed to LLM prompts.
- Modular AI runtime with strict interfaces and replaceable providers/deployers.

## 2) Monorepo Structure

```text
frontend/      # Next.js + TypeScript + Tailwind + shadcn/ui + Framer Motion
backend/       # FastAPI + SQLAlchemy 2 + Alembic + Redis + JWT + Pydantic v2
agents/        # AI runtime modules (planner/coder/tester/deployer/etc)
deployment/    # Container/deployment adapters and reverse-proxy templates
infra/         # docker-compose, local infra, env templates
shared/        # shared schemas/constants/types between services (codegen-ready)
docs/          # architecture, ADRs, API docs, UX specs
tests/         # integration/e2e/performance/security tests
scripts/       # dev scripts, seeding, migration helpers, tooling
```

## 3) High-Level System Design

### Frontend (`frontend`)
- App router based Next.js UI.
- Talks only to FastAPI REST endpoints (+ SSE/WebSocket for streaming chat).
- Main surfaces:
  - Landing page (premium animated experience).
  - Auth pages.
  - Dashboard shell (sidebar + views).
  - Project workspace (chat, deployments, logs, settings).

### Backend API (`backend`)
- FastAPI modular services with dependency injection.
- Responsibilities:
  - Auth/session lifecycle.
  - Projects/chats/messages CRUD.
  - Credits accounting.
  - AI orchestration API surface.
  - Deployment job orchestration.
  - Telegram secret handling and execution hooks.
  - Audit, logs, usage tracking.

### AI Runtime (`agents`)
- Backend-internal orchestration layer (not directly exposed to frontend).
- Split by modules:
  - `planner`: transforms user intent into execution plan.
  - `coder`: applies code generation/refactors.
  - `tester`: runs tests and static checks.
  - `deployer`: triggers deployment workflow.
  - `conversation`: manages response framing/streaming.
  - `provider`: provider abstraction (OpenAI/Anthropic/Gemini/OpenRouter).
  - `memory`: project/session memory retrieval and persistence.
  - `tools`: backend-safe tool interfaces called by agents.

### Deployment Runtime (`deployment`)
- Adapter abstraction over deployment backends (start with Docker).
- Project isolation:
  - Filesystem isolation.
  - Network isolation.
  - Environment isolation.
  - Log isolation.
- Reverse proxy/subdomain integration:
  - `project-slug.my-domain.com`
  - Provider-agnostic config model for Nginx/Traefik/Caddy adapters.

## 4) Service Boundaries and Data Flow

1. User sends message in project chat (frontend).
2. Frontend posts to backend chat endpoint.
3. Backend validates auth/permissions/credits and persists user message.
4. Backend hands off to AI orchestrator (`agents/conversation`).
5. Orchestrator calls planner -> coder -> tester -> deployer (as needed), using tool interfaces.
6. Tool calls execute in backend-controlled environment (never raw secrets in prompts).
7. Stream tokens/events back to frontend.
8. Persist assistant messages, artifacts, deployment status, git commits, logs.

## 5) Backend Module Layout

```text
backend/src/
  api/
    v1/
      routers/
      dependencies/
      dto/
  core/
    config.py
    security.py
    exceptions.py
  db/
    base.py
    session.py
    models/
    repositories/
    migrations/        # Alembic
  services/
    auth/
    users/
    projects/
    chat/
    deployments/
    credits/
    secrets/
    providers/
  integrations/
    redis/
    telegram/
  workers/
    jobs/
  main.py
```

## 6) AI Runtime Interfaces (Contract-First)

```python
# agents/interfaces.py (conceptual)
from typing import Protocol, AsyncIterator

class Planner(Protocol):
    async def plan(self, *, project_id: str, user_goal: str, context: dict) -> dict: ...

class Coder(Protocol):
    async def execute(self, *, plan: dict, workspace_path: str) -> dict: ...

class Tester(Protocol):
    async def run(self, *, workspace_path: str, test_plan: dict) -> dict: ...

class Deployer(Protocol):
    async def deploy(self, *, project_id: str, artifact_ref: str, config: dict) -> dict: ...

class ConversationEngine(Protocol):
    async def stream_reply(self, *, chat_id: str, user_message: str) -> AsyncIterator[str]: ...

class ProviderClient(Protocol):
    async def stream(self, *, messages: list[dict], model: str, tools: list[dict]) -> AsyncIterator[str]: ...

class MemoryStore(Protocol):
    async def recall(self, *, project_id: str, query: str) -> list[dict]: ...
    async def remember(self, *, project_id: str, item: dict) -> None: ...

class ToolExecutor(Protocol):
    async def call(self, *, name: str, args: dict, actor_id: str) -> dict: ...
```

## 7) Database Model (MVP)

- `users`
  - id (uuid), email (unique), password_hash, is_verified, role, credits_balance, created_at, updated_at
- `refresh_tokens`
  - id, user_id, token_hash, expires_at, revoked_at
- `projects`
  - id (uuid), user_id, type (`telegram_bot` | `website`), name, description, status, deployment_url, created_at, updated_at
- `chats`
  - id, project_id, title, created_at, updated_at
- `messages`
  - id, chat_id, role, content_markdown, metadata_json, created_at
- `deployments`
  - id, project_id, status, image_ref, container_id, logs_ref, started_at, finished_at
- `secrets`
  - id, project_id, key, encrypted_value, kms_key_id, created_at, updated_at
- `ai_providers`
  - id, name, model, is_default, config_json, created_at, updated_at
- `git_commits`
  - id, project_id, commit_hash, message, diff_summary, created_at
- `logs`
  - id, project_id, source, level, message, metadata_json, created_at

## 8) API Design Principles

- Base path: `/api/v1`
- Versioned routers and DTO layer separation from ORM models.
- Auth:
  - `POST /auth/register`
  - `POST /auth/login`
  - `POST /auth/refresh`
  - `POST /auth/logout`
  - `POST /auth/forgot-password`
  - `POST /auth/verify-email`
  - `POST /auth/reset-password`
- Projects:
  - `GET /projects`
  - `POST /projects`
  - `GET /projects/{project_id}`
  - `PATCH /projects/{project_id}`
- Chat:
  - `GET /projects/{project_id}/chats`
  - `POST /projects/{project_id}/chats/{chat_id}/messages`
  - `GET /projects/{project_id}/chats/{chat_id}/stream` (SSE)
- Deployments:
  - `POST /projects/{project_id}/deploy`
  - `GET /projects/{project_id}/deployments`
- Secrets:
  - `POST /projects/{project_id}/secrets`
  - `DELETE /projects/{project_id}/secrets/{secret_id}`

## 9) Security Architecture

- JWT access + refresh token rotation.
- Secret encryption at rest (envelope encryption abstraction).
- Token redaction middleware for logs/events.
- Rate limiting via Redis.
- Strict input validation with Pydantic v2 DTOs.
- LLM tool execution allowlist (explicitly registered tools only).
- Container sandbox limits (CPU/memory/network policies for each project).
- RBAC-ready policy hooks (`role`, `resource`, `action` checks).

## 10) Frontend UX Architecture

- Design language:
  - Dark-first palette.
  - Large type scale and breathing room.
  - Subtle gradients and glass surfaces.
  - Motion focused on context transitions (not decorative noise).
- Shared UI primitives:
  - Buttons, cards, panels, command palette, animated list transitions.
- Core routes:
  - `/` landing
  - `/auth/*`
  - `/app` dashboard
  - `/app/projects/[id]`
  - `/app/projects/[id]/chat`
  - `/app/projects/[id]/deployments`

## 11) Credits and Product Rules

- On registration: initialize each user with `1_000_000_000` credits.
- Credits decremented by AI usage units (model-dependent multiplier, configurable).
- Prevent execution when credits <= 0, with clear UX messaging.

## 12) MVP Execution Order (Strict)

1. Architecture design (this document).
2. Folder scaffolding and base configs.
3. Backend foundation (FastAPI, DB, migrations, Redis, health).
4. Frontend foundation (Next.js, Tailwind, shadcn/ui, motion design system).
5. Authentication and session flows.
6. Projects and dashboard pages.
7. AI chat streaming + conversation persistence.
8. Deployment abstraction + Docker adapter.
9. Telegram bot flow + encrypted secret management.
10. Website generation/deployment flow.

## 13) Step 1 Verification Checklist

- [x] Monorepo structure and module boundaries defined.
- [x] AI modules and interfaces explicitly split.
- [x] Backend stack requirements mapped to architecture.
- [x] Frontend stack and UX direction documented.
- [x] Data model and API surface outlined.
- [x] Security constraints captured (secrets isolation, rate limiting, RBAC-ready).
- [x] Iterative implementation order aligned to request.

## 14) Codex Execution Isolation

Every coding-agent turn on the `openai` path runs the actual Codex CLI in its own throwaway
Docker container (`backend/src/services/agent/codex_worker.py`), launched fresh per turn and
removed when it finishes - not a single long-lived container that every turn `docker exec`s into.

- **Filesystem**: the container gets *only* the current project's own subdirectory bind-mounted,
  at `/workspace` - resolved at run time from the shared projects volume's real host path, so no
  compose/volume changes (and no data migration) were needed to adopt this. A turn for one
  project cannot `cd`/read/write into another project's files; that path simply isn't mounted.
  If the volume's host path can't be resolved on a given deployment (see the production
  checklist), the run falls back to the pre-isolation full-tree mount rather than failing
  outright - loudly logged, not silent.
- **Docker access**: Codex still runs `docker build`/`docker run` itself as part of testing a
  project (see the bridge instructions in `codex_runtime.py`). By default this still goes through
  the raw host socket, same trust level as before. Setting `CODEX_DOCKER_HOST` to a
  `docker-socket-proxy` address (service included in `docker-compose.yml`, off by default)
  narrows this to a vetted subset of the Docker API instead of the full daemon - opt-in, since it
  needs the proxy service verified reachable first.
- **Not covered yet**: the Docker daemon (raw or proxied) is still shared across every project's
  containers, so this stops cross-project *file* access but not a Codex turn naming another
  project's *container* through that same daemon. Stronger isolation (gVisor, microVM-based
  sandboxes) is a further step, not required to get the filesystem-isolation win above.
