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
    "дашборд",
    "личный кабинет",
    "лк",
)

_SITE_WHOLE_WORDS = (
    "web",
    "веб",
    # "интерфейс" is too ambiguous (Telegram button UIs, bot menus) to count as a site signal.
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


def _workspace_has_site(root: Path) -> bool:
    return (root / "public" / "index.html").exists()


def _workspace_has_bot(root: Path) -> bool:
    return (root / "app.py").exists() or (root / "bot.py").exists()


def workspace_root_for(project: Project) -> Path:
    from src.services.workspace import project_dir

    return project_dir(project.id)


def can_update_project_type(project: Project) -> bool:
    """Allow reclassification until real bot/site files exist."""
    if project.status == "created":
        return True
    root = workspace_root_for(project)
    return not _workspace_has_site(root) and not _workspace_has_bot(root)


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


def reconcile_type_with_workspace(
    project: Project,
    workspace: Path | None = None,
    *,
    has_bot_secret: bool = False,
) -> bool:
    """Fix type when workspace/secrets clearly indicate bot-only (no site).

    Covers false `mixed`/`website` classifications that still show the subdomain card
    for projects that never generated a website.
    """
    if project.type == ProjectType.telegram_bot:
        return False

    root = workspace if workspace is not None else workspace_root_for(project)
    has_site = _workspace_has_site(root)
    has_bot_files = _workspace_has_bot(root)

    if has_site:
        if not has_bot_files and project.type == ProjectType.mixed:
            project.type = ProjectType.website
            return True
        return False

    # No site entrypoint on disk.
    if has_bot_files and project.type in (ProjectType.mixed, ProjectType.website):
        project.type = ProjectType.telegram_bot
        project.deploy_subdomain = None
        return True

    # website + TELEGRAM_BOT_TOKEN and no site files is inconsistent (token is only
    # requested for bot/mixed). Do not auto-demote intentional mixed before generation.
    if has_bot_secret and project.type == ProjectType.website:
        project.type = ProjectType.telegram_bot
        project.deploy_subdomain = None
        return True

    return False


# Backwards-compatible alias used by older call sites / tests.
def reconcile_mixed_type_without_website(project: Project, workspace: Path | None = None) -> bool:
    return reconcile_type_with_workspace(project, workspace)
