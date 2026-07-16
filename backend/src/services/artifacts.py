from __future__ import annotations

import html
import json
import re
import shutil
import textwrap
from pathlib import Path
from uuid import UUID

import docker
from docker.errors import BuildError, DockerException
from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models.project import Project
from src.db.models.secret import Secret
from src.services.project_git import with_project_git_lock
from src.services.secrets import TELEGRAM_BOT_TOKEN_KEY, decrypt_secret, normalize_secret_key


class ArtifactError(RuntimeError):
    pass


def _root() -> Path:
    root = Path(settings.generated_projects_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _project_dir(project_id: UUID | str) -> Path:
    safe_id = str(project_id)
    if not re.fullmatch(r"[a-fA-F0-9-]{32,36}", safe_id):
        raise ArtifactError("Invalid project id for artifact path")
    path = _root() / safe_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean_project_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _image_tag(project: Project) -> str:
    prefix = {"website": "site", "telegram_bot": "bot", "mixed": "mixed"}.get(project.type, "app")
    return f"airuntime-generated-{prefix}-{str(project.id)[:12]}:latest"


def _prompt_lines(project: Project, prompt: str) -> list[str]:
    source = prompt.strip() or project.description.strip() or project.name
    parts = re.split(r"[\n.;!?]+", source)
    lines = [part.strip(" -") for part in parts if part.strip(" -")]
    return lines[:6] or [project.name]


def _safe_title(project: Project) -> str:
    return html.escape(project.name.strip() or "AIRuntime project")


def generate_website_artifact(project: Project, prompt: str = "") -> Path:
    path = _project_dir(project.id)
    _clean_project_dir(path)
    _write_website_content(project, prompt, path)
    (path / "Dockerfile").write_text(
        "FROM nginx:1.27-alpine\nCOPY public/ /usr/share/nginx/html/\n",
        encoding="utf-8",
    )
    return path


def _write_website_content(project: Project, prompt: str, path: Path) -> None:
    public_dir = path / "public"
    public_dir.mkdir(parents=True, exist_ok=True)

    title = _safe_title(project)
    prompt_lines = [html.escape(line) for line in _prompt_lines(project, prompt)]
    lead = html.escape(
        project.description.strip() or prompt.strip() or "Проект, собранный AIRuntime."
    )
    default_features = [
        html.escape("Понимает задачу и стиль"),
        html.escape("Собирает лендинг с готовой структурой"),
        html.escape("Готовит деплой под домен"),
        html.escape("Обновляет проект по новому запросу"),
        html.escape("Упаковывает в контейнер и запускает"),
        html.escape("Фокус на скорости и результате"),
    ]
    features_list = (prompt_lines[:4] + default_features)[:6]
    features = "\n".join(
        f"<li><span>{index:02d}</span><p>{line}</p></li>"
        for index, line in enumerate(features_list, 1)
    )

    index_html = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #081426;
      --muted: #627086;
      --sky: #2388ff;
      --cyan: #18c7ca;
      --mint: #6ee7b7;
      --line: rgba(35, 136, 255, .14);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        linear-gradient(rgba(35,136,255,.055) 1px, transparent 1px),
        linear-gradient(90deg, rgba(35,136,255,.055) 1px, transparent 1px),
        linear-gradient(135deg, #fff 0%, #f3faff 54%, #eafff9 100%);
      background-size: 42px 42px, 42px 42px, auto;
    }}
    main {{
      width: min(1080px, calc(100% - 32px));
      margin: 0 auto;
      padding: 56px 0;
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 76px;
    }}
    .brand {{
      font-weight: 800;
      letter-spacing: .24em;
      font-size: 13px;
    }}
    .badge {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 8px 12px;
      color: var(--sky);
      background: rgba(255,255,255,.75);
      font-size: 13px;
      font-weight: 700;
    }}
    .ai-badge {{
      background: rgba(255,255,255,.85);
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.1fr .9fr;
      gap: 48px;
      align-items: center;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(44px, 8vw, 92px);
      line-height: .96;
      letter-spacing: 0;
    }}
    .gradient {{
      background: linear-gradient(120deg, var(--sky), var(--cyan), var(--mint));
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }}
    .lead {{
      margin: 24px 0 0;
      max-width: 680px;
      color: var(--muted);
      font-size: clamp(17px, 2vw, 21px);
      line-height: 1.65;
    }}
    .muted {{
      color: var(--muted);
      line-height: 1.6;
      font-size: 14px;
    }}
    .sublead {{
      margin: 18px 0 0;
      color: rgba(98, 112, 134, .98);
      font-weight: 600;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,.82);
      box-shadow: 0 24px 80px rgba(56,112,180,.16);
      padding: 24px;
    }}
    ul {{
      list-style: none;
      display: grid;
      gap: 12px;
      padding: 0;
      margin: 0;
    }}
    li {{
      display: grid;
      grid-template-columns: 44px 1fr;
      gap: 14px;
      align-items: start;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fff;
      padding: 14px;
    }}
    li span {{
      color: var(--sky);
      font-weight: 800;
      font-size: 12px;
      letter-spacing: .16em;
    }}
    li p {{ margin: 0; color: var(--muted); line-height: 1.5; }}
    .panel-title {{
      margin: 0 0 16px;
      font-size: 14px;
      font-weight: 800;
      letter-spacing: .08em;
      color: rgba(35, 136, 255, .95);
      text-transform: uppercase;
    }}
    .cta {{
      display: inline-flex;
      margin-top: 34px;
      border-radius: 12px;
      padding: 15px 22px;
      background: linear-gradient(120deg, var(--sky), var(--cyan), var(--mint));
      color: #fff;
      font-weight: 800;
      text-decoration: none;
      box-shadow: 0 16px 35px rgba(35,136,255,.22);
    }}
    .section {{
      margin-top: 64px;
      padding-top: 26px;
    }}
    h2 {{
      margin: 0 0 18px;
      font-size: 20px;
      letter-spacing: -.01em;
    }}
    .grid-3 {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
    }}
    .card {{
      border: 1px solid var(--line);
      background: rgba(255,255,255,.78);
      border-radius: 16px;
      padding: 18px;
    }}
    .card strong {{
      display: block;
      font-size: 14px;
      margin-bottom: 10px;
    }}
    .pill-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .pill {{
      border-radius: 999px;
      border: 1px solid var(--line);
      padding: 10px 14px;
      background: rgba(255,255,255,.78);
      color: rgba(8, 20, 38, .9);
      font-weight: 700;
      font-size: 13px;
    }}
    details {{
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255,255,255,.78);
      padding: 14px 16px;
      margin-bottom: 10px;
    }}
    summary {{
      cursor: pointer;
      font-weight: 800;
    }}
    details p {{
      margin: 10px 0 0;
      color: var(--muted);
      line-height: 1.6;
    }}
    footer {{
      margin-top: 92px;
      color: #8a96a8;
      font-size: 13px;
      text-align: center;
    }}
    @media (max-width: 820px) {{
      header {{ margin-bottom: 48px; }}
      .hero {{ grid-template-columns: 1fr; }}
      .grid-3 {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="brand">AIRUNTIME</div>
      <div class="badge ai-badge">AI-лендинг</div>
    </header>
    <section class="hero">
      <div>
        <h1>{title}<br><span class="gradient">собран AI</span></h1>
        <p class="lead">{lead}</p>
        <p class="sublead">AIRuntime автоматически упакует идею и запустит ее на вашем домене.</p>
        <a class="cta" href="mailto:hello@example.com">Попросить сборку</a>
      </div>
      <div class="panel">
        <p class="panel-title">Что получает продукт</p>
        <ul>{features}</ul>
      </div>
    </section>
    <section class="section">
      <h2>Как работает AIRuntime</h2>
      <div class="grid-3">
        <div class="card">
          <strong>1. Описание в чате</strong>
          <div class="muted">Расскажите, какой сайт нужен и какой стиль хотите.</div>
        </div>
        <div class="card">
          <strong>2. Генерация структуры</strong>
          <div class="muted">Платформа соберет контентные блоки и упакует UI.</div>
        </div>
        <div class="card">
          <strong>3. Деплой на домен</strong>
          <div class="muted">Запуск выполняется на стороне runtime и доступен по HTTPS.</div>
        </div>
      </div>
    </section>
    <section class="section">
      <h2>Кому подойдет</h2>
      <div class="pill-row">
        <span class="pill">MVP за 1-2 итерации</span>
        <span class="pill">Лендинг продукта</span>
        <span class="pill">Студия и услуги</span>
        <span class="pill">Сервисы и промо</span>
        <span class="pill">Агентские проекты</span>
      </div>
    </section>
    <section class="section">
      <h2>FAQ</h2>
      <details>
        <summary>Можно ли менять поддомен?</summary>
        <p>Да. Откройте настройки проекта и укажите нужный поддомен — при следующем запуске он применится.</p>
      </details>
      <details>
        <summary>Нужно ли уметь верстать?</summary>
        <p>Не обязательно. Вы задаете цель, а AIRuntime собирает шаблон и структуру сайта.</p>
      </details>
      <details>
        <summary>Как быстро появится сайт?</summary>
        <p>Обычно в пределах минут — после генерации запускается деплой в runtime.</p>
      </details>
    </section>
    <footer>Сайт сгенерирован AIRuntime из описания проекта.</footer>
  </main>
</body>
</html>
"""
    (public_dir / "index.html").write_text(index_html, encoding="utf-8")


def _telegram_token(db: Session, project: Project) -> str | None:
    rows = db.query(Secret).filter(Secret.project_id == project.id).all()
    for row in rows:
        if not row.encrypted_value:
            continue
        normalized_key = normalize_secret_key(row.key, project_type=project.type)
        if normalized_key == TELEGRAM_BOT_TOKEN_KEY:
            return decrypt_secret(row.encrypted_value)
    return None


def generate_telegram_bot_artifact(project: Project, prompt: str = "") -> Path:
    path = _project_dir(project.id)
    _clean_project_dir(path)
    _write_telegram_content(project, prompt, path)
    (path / "Dockerfile").write_text(_TELEGRAM_DOCKERFILE, encoding="utf-8")
    return path


_TELEGRAM_DOCKERFILE = "\n".join(
    [
        "FROM python:3.12-slim",
        "WORKDIR /app",
        "COPY requirements.txt .",
        "RUN pip install --no-cache-dir -r requirements.txt",
        "COPY app.py .",
        'CMD ["python", "app.py"]',
        "",
    ]
)

MIXED_DOCKERFILE = """FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends nginx \\
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY public/ /var/www/html/
RUN rm -f /etc/nginx/sites-enabled/default \\
    && printf 'server {\\n    listen 80;\\n    root /var/www/html;\\n    index index.html;\\n}\\n' > /etc/nginx/conf.d/site.conf
RUN printf '#!/bin/sh\\nset -e\\nnginx\\nexec python app.py\\n' > /docker-entrypoint.sh \\
    && chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
"""


def _write_telegram_content(project: Project, prompt: str, path: Path) -> None:
    safe_name = json.dumps(project.name, ensure_ascii=False)
    app_py = f"""
import logging
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

BOT_NAME = {safe_name}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.effective_user.first_name if update.effective_user else None
    greeting = f"Привет, {{user_name}}!" if user_name else "Привет!"
    await update.message.reply_text(
        f"{{greeting}} Я {{BOT_NAME}}. Уже на связи и готов помогать - просто напишите сообщение."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Спасибо! Я получил сообщение и передам его в рабочий сценарий проекта."
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
"""
    (path / "app.py").write_text(textwrap.dedent(app_py).strip() + "\n", encoding="utf-8")
    (path / "requirements.txt").write_text("python-telegram-bot==21.10\n", encoding="utf-8")


def generate_mixed_artifact(project: Project, prompt: str = "") -> Path:
    """A project that's both a website and a Telegram bot at once - one container running
    both, nginx serving the site in the background and the bot process in the foreground."""
    path = _project_dir(project.id)
    _clean_project_dir(path)
    _write_website_content(project, prompt, path)
    _write_telegram_content(project, prompt, path)
    (path / "Dockerfile").write_text(MIXED_DOCKERFILE, encoding="utf-8")
    return path


def generate_project_artifact(db: Session, project: Project, prompt: str = "") -> Path:
    needs_bot = project.type in ("telegram_bot", "mixed")
    if needs_bot and not _telegram_token(db, project):
        raise ArtifactError("Telegram bot requires TELEGRAM_BOT_TOKEN secret before deployment")
    if project.type == "website":
        return generate_website_artifact(project, prompt)
    if project.type == "telegram_bot":
        return generate_telegram_bot_artifact(project, prompt)
    if project.type == "mixed":
        return generate_mixed_artifact(project, prompt)
    raise ArtifactError(f"Unsupported project type: {project.type}")


def ensure_project_artifact(db: Session, project: Project, prompt: str = "") -> Path:
    path = _project_dir(project.id)
    if (path / "Dockerfile").exists():
        needs_bot = project.type in ("telegram_bot", "mixed")
        if needs_bot and not _telegram_token(db, project):
            raise ArtifactError("Telegram bot requires TELEGRAM_BOT_TOKEN secret before deployment")
        return path
    artifact_dir = generate_project_artifact(db, project, prompt)
    try:
        # Create a baseline git snapshot for deployments started without chat generation.
        from src.services.project_git import commit_snapshot

        commit_snapshot(artifact_dir, message=f"Artifact generated: {project.name}")
    except Exception:
        # Git is best-effort; deployment flow should not fail.
        pass
    return artifact_dir


def _docker_build(path: Path, tag: str) -> None:
    client = docker.from_env()
    client.images.build(path=str(path), tag=tag, rm=True, pull=False)


def _build_error_message(exc: DockerException) -> str:
    if isinstance(exc, BuildError):
        details: list[str] = []
        for item in exc.build_log or []:
            if isinstance(item, dict):
                stream = item.get("stream") or item.get("error") or ""
                if stream:
                    details.append(str(stream).strip())
        if details:
            return "\n".join(details[-20:])
    return str(exc)


def try_build_project_image(project: Project) -> dict:
    """Raw build attempt against the project's current files, no AI auto-repair - backs the
    interactive build_project agent tool (src/services/agent/tools.py) so the agent can see a
    real build log and fix things itself mid-conversation, instead of only reacting to the
    automatic build-then-repair pipeline that runs after its turn ends (build_project_image
    below, which does include AI auto-repair)."""
    path = _project_dir(project.id)
    if not (path / "Dockerfile").exists():
        return {"ok": False, "log": "No Dockerfile in the project yet - write one before building."}
    tag = _image_tag(project)
    try:
        with with_project_git_lock(project.id):
            _docker_build(path, tag)
    except DockerException as exc:
        return {"ok": False, "log": _build_error_message(exc)}
    return {"ok": True, "log": f"Build succeeded: {tag}"}


def build_project_image(
    db: Session, project: Project, prompt: str = ""
) -> tuple[str, dict[str, str], bool]:
    """Returns (image_tag, environment, used_fallback). used_fallback is True when the agent's
    own code failed to build and even AI repair couldn't fix it in time, so the deterministic
    placeholder template was deployed instead - callers must tell the user this happened, since
    it silently replaces whatever real logic the agent had written with a generic stub."""
    used_fallback = False
    # Prevent races between git checkout/commit and docker builds.
    with with_project_git_lock(project.id):
        path = ensure_project_artifact(db, project, prompt)
        tag = _image_tag(project)
        try:
            _docker_build(path, tag)
        except DockerException as exc:
            last_error = _build_error_message(exc)
            fixed = False

            from src.services.agentic_artifacts import (
                REPAIR_ATTEMPTS,
                repair_artifact_with_agent,
                repair_artifact_with_fallback,
            )

            for _attempt in range(REPAIR_ATTEMPTS):
                try:
                    repaired_path = repair_artifact_with_agent(db, project, last_error)
                    db.commit()
                    _docker_build(repaired_path, tag)
                    fixed = True
                    break
                except DockerException as retry_exc:
                    last_error = _build_error_message(retry_exc)
                except ArtifactError:
                    # No AI provider configured, or the agent produced nothing usable -
                    # stop retrying with AI and fall through to the deterministic template.
                    break

            if not fixed:
                used_fallback = True
                try:
                    repaired_path = repair_artifact_with_fallback(db, project, last_error)
                    db.commit()
                    _docker_build(repaired_path, tag)
                except DockerException as second_exc:
                    second_error = _build_error_message(second_exc)
                    raise ArtifactError(
                        f"Docker image build failed after repair:\n{second_error}"
                    ) from second_exc
                except Exception as repair_exc:
                    raise ArtifactError(
                        f"Docker image build failed and repair did not complete:\n{last_error}\n{repair_exc}"
                    ) from repair_exc

    environment: dict[str, str] = {}
    if project.type in ("telegram_bot", "mixed"):
        token = _telegram_token(db, project)
        if not token:
            raise ArtifactError("Telegram bot token is missing")
        environment["TELEGRAM_BOT_TOKEN"] = token
    return tag, environment, used_fallback
