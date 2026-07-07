# AIRuntime MVP

AIRuntime — платформа AI-рантайма, где пользователи создают софт через диалог, а платформа планирует, пишет, тестирует и деплоит проекты.

## Стек

- Frontend: Next.js, TypeScript, TailwindCSS, UI-примитивы в стиле shadcn, Framer Motion
- Backend: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Redis, JWT, Pydantic v2
- AI runtime: модульные агенты (`planner`, `coder`, `tester`, `deployer`, `conversation`, `provider`, `memory`, `tools`)

## Монорепозиторий

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

## Быстрый старт

1. Скопируйте `.env.example` в `.env` и настройте значения.
2. Запустите:
   - `docker compose up --build`
3. Сервисы:
   - Frontend: `http://localhost:3000`
   - Backend: `http://localhost:8000`
   - OpenAPI: `http://localhost:8000/api/v1/openapi.json`

## Локальная разработка backend

```bash
cd backend
python -m venv .venv
. .venv/bin/activate  # или .venv\Scripts\activate в Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload
```

## Локальная разработка frontend

```bash
cd frontend
npm install
npm run dev
```

## Продакшен

Требования к запуску и проверенный статус — в `docs/production-checklist.md`.

Запуск CI локально:

```bash
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cd backend && alembic upgrade head && cd ..
pytest tests -q
cd frontend && npm ci && npm run lint && npm run build
```

## Реализованные возможности MVP

- Премиальный анимированный лендинг (Hero, Features, How it works, Examples, Pricing, FAQ, CTA, Footer)
- Auth API: регистрация, вход, ротация refresh-токенов, отзыв при logout, verify-email, сброс пароля
- Новым пользователям начисляется `1 000 000 000` кредитов
- Dashboard с сайдбаром и страницами проектов, чата и настроек
- Projects API (создание / список / получение)
- Project chat API с SSE-стримингом
- Абстракция провайдеров с выбором OpenAI / Anthropic / Gemini / OpenRouter
- Абстракция деплоя и Docker-адаптер
- Очередь деплоев на Redis и фоновый worker
- Telegram token flow с шифрованным хранением
- Secrets API и граница редактирования секретов
- Security middleware: trusted hosts, ограниченный CORS, security headers, rate limiting

## Примечания

- Секреты шифруются перед сохранением и никогда не попадают в промпты LLM.
- Frontend общается только с FastAPI.
- AI-модули разнесены по отдельным папкам и интерфейсам.
