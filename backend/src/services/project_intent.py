from src.api.dto.project import ProjectType
from src.db.models.project import Project

_BOT_TERMS = (
    "telegram",
    "телеграм",
    "тг",
    "бот",
    "bot",
    "webhook",
    "polling",
)

_SITE_TERMS = (
    "сайт",
    "лендинг",
    "landing",
    "web",
    "website",
    "страниц",
    "интерфейс",
    "дашборд",
    "личный кабинет",
    "лк",
)


def infer_project_type(text: str) -> ProjectType:
    normalized = text.lower()
    bot_score = sum(1 for term in _BOT_TERMS if term in normalized)
    site_score = sum(1 for term in _SITE_TERMS if term in normalized)
    if bot_score > site_score:
        return ProjectType.telegram_bot
    return ProjectType.website


def update_project_type_from_prompt(project: Project, prompt: str) -> bool:
    inferred = infer_project_type(prompt)
    if project.type == inferred:
        return False
    project.type = inferred
    if inferred != ProjectType.website:
        project.deploy_subdomain = None
    return True

