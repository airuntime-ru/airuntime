import re

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


def _count_word_matches(terms: tuple[str, ...], text: str) -> int:
    # Match at a word start (not anywhere mid-word - a plain "in" check would count ordinary
    # words like "работа"/"работало" as bot signals, since they contain "бот" as a substring),
    # but allow anything after the term so inflected forms still count ("бота", "боту", ...).
    return sum(1 for term in terms if re.search(rf"\b{re.escape(term)}\w*", text))


def infer_project_type(text: str) -> ProjectType:
    normalized = text.lower()
    bot_score = _count_word_matches(_BOT_TERMS, normalized)
    site_score = _count_word_matches(_SITE_TERMS, normalized)
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

