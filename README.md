# AIRuntime MVP

AIRuntime is an AI runtime platform where users build software by conversation while the platform plans, writes, tests, and deploys projects.

## Stack

- Frontend: Next.js, TypeScript, TailwindCSS, shadcn-style UI primitives, Framer Motion
- Backend: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Redis, JWT, Pydantic v2
- AI runtime: modular agents (`planner`, `coder`, `tester`, `deployer`, `conversation`, `provider`, `memory`, `tools`)

## Monorepo

```text
frontend/
backend/
deployment/
agents/
infra/
shared/
docs/
tests/
scripts/
```

## Quick Start

1. Copy `.env.example` into `.env` and adjust values.
2. Run:
   - `docker compose up --build`
3. Services:
   - Frontend: `http://localhost:3000`
   - Backend: `http://localhost:8000`
   - OpenAPI: `http://localhost:8000/api/v1/openapi.json`

## Backend Local Development

```bash
cd backend
python -m venv .venv
. .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload
```

## Frontend Local Development

```bash
cd frontend
npm install
npm run dev
```

## Production

See `docs/production-checklist.md` for launch requirements and verified status.

Run CI locally:

```bash
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cd backend && alembic upgrade head && cd ..
pytest tests -q
cd frontend && npm ci && npm run lint && npm run build
```

## Implemented MVP Features

- Premium animated landing page (Hero, Features, How it works, Examples, Pricing, FAQ, CTA, Footer)
- Auth APIs: register, login, refresh rotation, logout revocation, verify-email, reset-password flows
- New users receive `1,000,000,000` credits
- Dashboard shell with sidebar and project/chat/settings pages
- Projects API (create/list/get)
- Project chat API with SSE streaming endpoint
- Provider abstraction with OpenAI/Anthropic/Gemini/OpenRouter selectable config
- Deployment abstraction and Docker deployment adapter
- Redis-backed deployment queue and background deployment worker
- Telegram token flow with encrypted storage abstraction
- Secrets API and secret redaction boundary
- Security middleware: trusted hosts, restrictive CORS, security headers, rate limiting

## Notes

- Secrets are encrypted before persistence and never sent to LLM prompts.
- Frontend communicates only with FastAPI.
- AI modules are split into dedicated folders/interfaces.
