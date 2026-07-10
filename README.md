# AIRuntime

AIRuntime — платформа, где пользователь описывает сайт или Telegram-бота в чате, а AI-агент пишет код, коммитит его в git и деплоит рабочую версию в Docker-контейнере.

## Стек

- **Frontend**: Next.js (App Router), TypeScript, Tailwind v4, кастомные UI-примитивы
- **Backend**: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Redis, JWT-аутентификация, Pydantic v2
- **Admin**: Django admin-панель (отдельное приложение, читает/пишет те же таблицы Postgres)
- **AI-агент**: `backend/src/services/agent/` — провайдеро-независимый tool-calling цикл (OpenAI/Anthropic/Gemini/OpenRouter)
- **Деплой проектов**: каждый сгенерированный проект — отдельный Docker-контейнер, поднимаемый воркером через Docker Engine API
- **Хранилище файлов**: MinIO (S3-совместимое)
- **Почта**: свой SMTP (docker-mailserver в проде) для писем логина/сброса пароля/биллинга

## Структура репозитория

```text
backend/    FastAPI-приложение: API, воркер, миграции, сервисы, агент
frontend/   Next.js-приложение (личный кабинет + лендинг)
admin/      Django admin-панель (управление пользователями, тарифами, модерацией)
infra/      Конфигурация Traefik, почтового сервера и т.п. для продакшена
scripts/    Вспомогательные скрипты: сид данных, smoke-test, настройка DNS/почты на сервере
tests/      pytest-тесты backend (API, деплой-адаптер, git, артефакты и т.д.)
docs/       Ранние планировочные документы (см. предупреждение ниже)
shared/     Общие схемы/константы (задел на будущее, пока почти пусто)
```

> **О `docs/architecture.md` и `docs/production-checklist.md`**: это документы с самого начала проекта (Step 1 планирование). Часть описанной там структуры (`agents/`, отдельные `planner`/`coder`/`tester`/`deployer` модули) в итоге не была реализована в таком виде — вся агентная логика живёт в `backend/src/services/agent/`. Не полагайтесь на эти файлы как на текущую истину; этот README и код — источник актуальной информации.

## Быстрый старт (Docker Compose)

1. Скопируйте `.env.example` в `.env` и заполните как минимум один провайдер (`OPENAI_API_KEY` и т.д.) — без него агент не сможет отвечать в чате.
2. Запустите:
   ```bash
   docker compose up --build
   ```
3. Сервисы:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000, OpenAPI: http://localhost:8000/api/v1/openapi.json
   - Django admin: http://localhost:8001 (суперпользователь создаётся автоматически по `DJANGO_SUPERUSER_EMAIL`/`DJANGO_SUPERUSER_PASSWORD` из `.env`)
   - MinIO консоль: http://localhost:9001

Контейнеры: `postgres`, `redis`, `minio` (+`minio-init`), `backend` (API), `worker` (Redis-очереди деплоя и биллинга, единственный сервис с доступом к `/var/run/docker.sock` помимо admin), `django-admin`, `frontend`.

## Локальная разработка без Docker

### Backend

```bash
cd backend
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
uvicorn src.main:app --reload
```

Воркер (обработка деплоев и периодический биллинг-свип) запускается отдельно:

```bash
python -m src.workers.deployment_worker
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Admin (Django)

```bash
cd admin
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8001
```

## Тесты и линтеры

```bash
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cd backend && alembic upgrade head && cd ..
pytest tests -q
ruff check backend/src tests scripts admin
ruff format --check backend/src tests scripts admin
cd frontend && npm ci && npm run lint && npm run build
```

CI (`.github/workflows/ci.yml`) прогоняет то же самое на каждый push/PR в `main`.

## Архитектурные заметки

- **Docker-доступ разделён по соображениям безопасности.** `backend` обслуживает интернет-трафик и исполняет tool-calling агента по указаниям LLM — ему **намеренно не примонтирован** `/var/run/docker.sock` (монтирование туда — путь к эскалации привилегий). Управление контейнерами сгенерированных проектов (стоп/удаление) идёт через синхронный Redis RPC (`backend/src/services/docker_control_queue.py`): backend кладёт задачу в очередь и блокируется на ключе результата, `worker` — единственный процесс с доступом к сокету — забирает задачу, выполняет и кладёт результат обратно.
- **Один проект = один Docker-контейнер.** Артефакты собираются в `backend/src/services/artifacts.py`, коммитятся в git (`services/project_git.py`), образ собирается и запускается через `services/deployment/docker_adapter.py`.
- **Секреты (токены ботов, ключи API)**: агент сам резервирует слот через tool `request_secret` (без значения), пользователь заполняет значение в UI. Хранится зашифрованно (`APP_ENCRYPTION_KEY`), никогда не попадает в промпт LLM.
- **Модерация**: каждый запрос на создание/изменение проекта проверяется классификатором (`services/moderation.py`) на признаки вредоносного содержимого; заблокированные проекты и история решений видны в Django admin.
- **Биллинг**: тарифы (`Plan`) настраиваются в Django admin — месячный лимит кредитов, лимит одновременных проектов, цена. Пополнение баланса — вручную (нет реальной платёжной интеграции): пользователь создаёт счёт, админ отмечает его оплаченным в Django admin, периодический воркер-свип (`services/billing.py`, каждые 5 минут в цикле воркера) начисляет кредиты и шлёт письмо. Та же задача продлевает тарифные периоды и шлёт предупреждения о низком балансе.

## Продакшен

Деплой на сервер идёт через `deploy.sh` (`git pull` → `docker compose -f docker-compose.prod.yml up -d --build` → миграции backend и admin → health-check). На сервере дополнительно настроен еженедельный cron (`docker_cleanup.sh`), чистящий устаревший Docker build cache — сам скрипт живёт на сервере в `/home/airuntime/`, не в репозитории.

Известное ограничение прод-окружения: VPS всего с 1.9 ГБ RAM — при добавлении новых тяжёлых сервисов в `docker-compose.prod.yml` следите за потреблением памяти (`free -h` на сервере, своп настроен на 4 ГБ как страховка).
