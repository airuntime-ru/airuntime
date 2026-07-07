from __future__ import annotations

import html
import json
import re
import textwrap
from pathlib import Path
from uuid import UUID

import docker
from docker.errors import DockerException
from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models.project import Project
from src.db.models.secret import Secret
from src.services.secrets import decrypt_secret

TOKEN_SECRET_KEYS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN", "BOT_TOKEN")


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


def _image_tag(project: Project) -> str:
    prefix = "site" if project.type == "website" else "bot"
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
    public_dir = path / "public"
    public_dir.mkdir(parents=True, exist_ok=True)

    title = _safe_title(project)
    lines = [html.escape(line) for line in _prompt_lines(project, prompt)]
    lead = html.escape(
        project.description.strip() or prompt.strip() or "Проект, собранный AIRuntime."
    )
    features = "\n".join(
        f"<li><span>{index:02d}</span><p>{line}</p></li>" for index, line in enumerate(lines, 1)
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
    footer {{
      margin-top: 92px;
      color: #8a96a8;
      font-size: 13px;
    }}
    @media (max-width: 820px) {{
      header {{ margin-bottom: 48px; }}
      .hero {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="brand">AIRUNTIME</div>
      <div class="badge">запущено</div>
    </header>
    <section class="hero">
      <div>
        <h1>{title}<br><span class="gradient">готов к запуску</span></h1>
        <p class="lead">{lead}</p>
        <a class="cta" href="mailto:hello@example.com">Связаться</a>
      </div>
      <div class="panel">
        <ul>{features}</ul>
      </div>
    </section>
    <footer>Сайт сгенерирован AIRuntime из описания проекта.</footer>
  </main>
</body>
</html>
"""
    (public_dir / "index.html").write_text(index_html, encoding="utf-8")
    (path / "Dockerfile").write_text(
        "FROM nginx:1.27-alpine\nCOPY public/ /usr/share/nginx/html/\n",
        encoding="utf-8",
    )
    return path


def _telegram_token(db: Session, project: Project) -> str | None:
    rows = db.query(Secret).filter(Secret.project_id == project.id).all()
    for row in rows:
        if row.key.upper() in TOKEN_SECRET_KEYS:
            return decrypt_secret(row.encrypted_value)
    return None


def generate_telegram_bot_artifact(project: Project, prompt: str = "") -> Path:
    path = _project_dir(project.id)
    safe_name = json.dumps(project.name, ensure_ascii=False)
    safe_description = json.dumps(
        (prompt or project.description or "AIRuntime bot").strip(), ensure_ascii=False
    )
    app_py = f"""
import logging
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

BOT_NAME = {safe_name}
DESCRIPTION = {safe_description}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"{{BOT_NAME}} запущен. {{DESCRIPTION}}")


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
    (path / "Dockerfile").write_text(
        "\n".join(
            [
                "FROM python:3.12-slim",
                "WORKDIR /app",
                "COPY requirements.txt .",
                "RUN pip install --no-cache-dir -r requirements.txt",
                "COPY app.py .",
                "CMD [\"python\", \"app.py\"]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def generate_project_artifact(db: Session, project: Project, prompt: str = "") -> Path:
    if project.type == "website":
        return generate_website_artifact(project, prompt)
    if project.type == "telegram_bot":
        if not _telegram_token(db, project):
            raise ArtifactError(
                "Telegram bot requires TELEGRAM_BOT_TOKEN secret before deployment"
            )
        return generate_telegram_bot_artifact(project, prompt)
    raise ArtifactError(f"Unsupported project type: {project.type}")


def ensure_project_artifact(db: Session, project: Project, prompt: str = "") -> Path:
    path = _project_dir(project.id)
    if (path / "Dockerfile").exists():
        if project.type == "telegram_bot" and not _telegram_token(db, project):
            raise ArtifactError(
                "Telegram bot requires TELEGRAM_BOT_TOKEN secret before deployment"
            )
        return path
    return generate_project_artifact(db, project, prompt)


def build_project_image(db: Session, project: Project, prompt: str = "") -> tuple[str, dict[str, str]]:
    path = ensure_project_artifact(db, project, prompt)
    tag = _image_tag(project)
    try:
        client = docker.from_env()
        client.images.build(path=str(path), tag=tag, rm=True, pull=False)
    except DockerException as exc:
        raise ArtifactError(f"Docker image build failed: {exc}") from exc

    environment: dict[str, str] = {}
    if project.type == "telegram_bot":
        token = _telegram_token(db, project)
        if not token:
            raise ArtifactError("Telegram bot token is missing")
        environment["TELEGRAM_BOT_TOKEN"] = token
    return tag, environment
