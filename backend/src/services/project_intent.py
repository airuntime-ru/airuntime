import re
from pathlib import Path

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

# Avoid a bare "web" prefix: `\bweb\w*` matches "webhook" and incorrectly marks bot-only
# prompts as mixed, which surfaces the subdomain settings card for projects without a site.
_SITE_TERMS = (
    "сайт",
    "лендинг",
    "landing",
    "website",
    "страниц",
    "интерфейс",
    "дашборд",
    "личный кабинет",
    "лк",
)

_SITE_WHOLE_WORDS = (
    "web",
    "веб",
)


def _count_word_matches(terms: tuple[str, ...], text: str) -> int:
    # Match at a word start (not anywhere mid-word - a plain "in" check would count ordinary
    # words like "работа"/"работало" as bot signals, since they contain "бот" as a substring),
    # but allow anything after the term so inflected forms still count ("бота", "боту", ...).
    return sum(1 for term in terms if re.search(rf"\b{re.escape(term)}\w*", text))


def _count_whole_word_matches(terms: tuple[str, ...], text: str) -> int:
    return sum(1 for term in terms if re.search(rf"\b{re.escape(term)}\b", text))


def detect_project_type_signals(text: str) -> tuple[int, int]:
    normalized = text.lower()
    bot_score = _count_word_matches(_BOT_TERMS, normalized)
    site_score = _count_word_matches(_SITE_TERMS, normalized) + _count_whole_word_matches(
        _SITE_WHOLE_WORDS, normalized
    )
    return bot_score, site_score


def infer_project_type(text: str) -> ProjectType:
    bot_score, site_score = detect_project_type_signals(text)
    if bot_score > 0 and site_score > 0:
        return ProjectType.mixed
    if bot_score > site_score:
        return ProjectType.telegram_bot
    if site_score > 0:
        return ProjectType.website
    # No signal yet - keep the historical create default so empty names still get a type.
    return ProjectType.website


def update_project_type_from_prompt(project: Project, prompt: str) -> bool:
    bot_score, site_score = detect_project_type_signals(prompt)
    if bot_score == 0 and site_score == 0:
        # A follow-up without type signals must not overwrite a correct bot/site classification
        # with the ambiguous website default.
        return False
    inferred = infer_project_type(prompt)
    if project.type == inferred:
        return False
    project.type = inferred
    if inferred == ProjectType.telegram_bot:
        project.deploy_subdomain = None
    return True


def reconcile_mixed_type_without_website(project: Project, workspace: Path | None = None) -> bool:
    """Downgrade mixed → telegram_bot when the workspace has no site entrypoint."""
    if project.type != ProjectType.mixed:
        return False
    root = workspace
    if root is None:
        from src.services.workspace import project_dir

        root = project_dir(project.id)
    if (root / "public" / "index.html").exists():
        return False
    # Only reconcile when the workspace already has bot files; otherwise the project may
    # still be empty / not generated yet and mixed remains a valid intent.
    if not (root / "app.py").exists() and not (root / "bot.py").exists():
        return False
    project.type = ProjectType.telegram_bot
    project.deploy_subdomain = None
    return True
