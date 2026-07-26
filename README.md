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
tests/      pytest-тесты backend (API, деплой-адаптер, git, артефакты и т.д.)
docs/       Ранние планировочные документы (см. предупреждение ниже)
shared/     Общие схемы/константы (задел на будущее, пока почти пусто)
```

> **О `docs/architecture.md` и `docs/production-checklist.md`**: это документы с самого начала проекта (Step 1 планирование). Часть описанной там структуры (`agents/`, отдельные `planner`/`coder`/`tester`/`deployer` модули) в итоге не была реализована в таком виде — вся агентная логика живёт в `backend/src/services/agent/`. Не полагайтесь на эти файлы как на текущую истину; этот README и код — источник актуальной информации.

## Быстрый старт (Docker Compose)

1. Скопируйте `.env.example` в `.env` и заполните как минимум один провайдер (`OPENAI_API_KEY` и т.д.) — без него агент не сможет отвечать в чате.
2. Соберите образ для просмотра в браузере (product-quality pipeline включён по умолчанию — см. раздел ниже; без этого шага просмотр в браузере будет просто честно возвращать «образ не собран», не ломая остальное):
   ```bash
   docker compose build preview
   ```
3. Запустите:
   ```bash
   docker compose up --build
   ```
4. Сервисы:
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

## Оркестрация агентов (единственный путь, без флагов)

Каждое сообщение в чат проходит через persistent-движок оркестрации (`backend/src/services/orchestration/`), а не через одиночный проход «опиши → напиши код → собери». Полный цикл:

```
запрос → анализ намерения → OrchestrationRun (строка в БД)
       → планировщик → версионированный DAG задач
       → маршрутизация каждой задачи: platform-операция | skill | MCP | специализированный агент
       → сбор фактических доказательств (реальный git diff, сборка, скан секретов)
       → детерминированная валидация → приём / repair / retry / replan
       → git-checkpoint → интеграция → сборка → деплой → проверка рантайма
```

**Никаких feature-флагов у этого нет.** Специализированные роли, skills, MCP, worktree-изоляция, replanning, preview/design-review — всё включено всегда. Единственные оставшиеся настройки — численные лимиты (`ORCHESTRATION_MAX_PLAN_TASKS`, `ORCHESTRATION_MAX_REPLANS`, `ORCHESTRATION_MAX_TASK_ATTEMPTS`, `ORCHESTRATION_RUN_LEASE_TTL_SECONDS`, `ORCHESTRATION_TASK_DEFAULT_TIMEOUT_SECONDS`), а не переключатели поведения.

Ключевые свойства:
- **Планы версионируются, не перезаписываются** — replanning создаёт новую версию, сохраняя уже принятые задачи.
- **Заявления модели ≠ доказательства** — `TaskResult` (что агент утверждает) хранится отдельно от `TaskEvidence` (что сервер проверил сам: git diff, результат сборки, скан секретов).
- **Права роли считает сервер** — модель не может расширить свои tools/пути; enforcement двухслойный (превентивный в `ScopedWorkspaceTools`, детективный в `validation.py` против реального diff).
- **Переживает рестарт** — run/план/задачи это строки в Postgres, а не in-memory состояние.
- **Ход виден в UI** — вкладка «Оркестрация» в проекте показывает план, статусы задач, роли, зависимости и позволяет остановить выполнение.

**Инфраструктурные сбои просмотра отделены от содержательных проблем.** Если просмотр не смог даже запуститься (воркер недоступен, образ не собран, Docker-ошибка, таймаут) — это не повод просить кодящего агента что-то «починить» правкой файлов: такие случаи распознаются отдельно и не тратят бюджет попыток задачи.

**Просмотр в браузере — изоляция сети.** `preview_project` никогда не получает от модели URL, хост или схему — только относительные пути вида `/services.html` (валидируются дважды: в `agent/tools.py` и в `preview_runner.py`). Контейнер просматриваемого проекта не публикуется на хост-порт и не получает Traefik-labels; он подключён к обычной приватной сети проекта (той же, что у Postgres/Redis-сайдкаров) плюс к отдельной сети с `internal=true`, к которой также подключён одноразовый контейнер Playwright. `internal=true` означает отсутствие маршрута наружу вообще — просмотрщик физически не может достучаться до интернета, Docker API или cloud-metadata, вне зависимости от того, какие пути попросила модель.

**Требуется отдельный образ.** Playwright не добавлен в `backend/Dockerfile` (общий для `backend` и `worker`), чтобы не тащить вес браузера в интернет-facing процесс. Вместо этого — `deployment/preview/Dockerfile`, тот же паттерн, что уже применялся для `codex`: собирается один раз, воркер поднимает свежий одноразовый контейнер на каждый вызов. Образ нужно собрать один раз на сервере (без него просмотр честно завершается «образ не собран», не ломая ход):
```bash
docker compose -f docker-compose.prod.yml build preview
```

**Скриншоты в ревью — по провайдерам.** До двух скриншотов (desktop + mobile главной страницы) читаются напрямую с диска и передаются в ревью-вызов через `provider.build_messages(..., images=...)` — тот же механизм, что уже кодирует изображения для Anthropic (base64 image-блок), OpenAI-совместимых (data-URI `image_url`) и Gemini (`inline_data`). Для openai/Codex-пути скриншоты **намеренно не передаются**: `codex_simple_complete` умеет прикладывать файлы через `--image`, но только если Codex-контейнеру примонтирован реальный workspace проекта — а это дало бы «независимому» ревьюеру тот же файловый/shell-доступ, что и у создающего агента, что противоречит самой идее отдельного ревью. Ревью на этом пути остаётся текстовым (брифа + структурированных находок просмотра всё ещё достаточно для большинства проверок, включая тот самый мета-текст на странице). Файл со скриншотом никогда не попадает в raw LLM prompt как часть текста — только как typed image-контент через `build_messages`.

**Наблюдаемость**: каждый ход с включённым пайплайном пишет структурированную строку в лог (`logger.info("pipeline_run_metrics %s", ...)`, длительности этапов/число итераций/оценки ревью/число инфраструктурных повторов) и — отдельно — строку в таблицу `pipeline_run_metrics` (миграция `0017`) для агрегатных запросов вроде «какой процент проектов прошёл ревью с первого раза».

## Продакшен

Деплой на сервер идёт через `deploy.sh` (`git pull` → `docker compose -f docker-compose.prod.yml up -d --build` → миграции backend и admin → health-check). На сервере дополнительно настроен еженедельный cron (`docker_cleanup.sh`), чистящий устаревший Docker build cache — сам скрипт живёт на сервере в `/home/airuntime/`, не в репозитории.

Известное ограничение прод-окружения: VPS всего с 1.9 ГБ RAM — при добавлении новых тяжёлых сервисов в `docker-compose.prod.yml` следите за потреблением памяти (`free -h` на сервере, своп настроен на 4 ГБ как страховка).
