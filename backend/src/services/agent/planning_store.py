"""Persist/load product-pipeline planning artifacts under a project's `.airuntime/planning/`.

That prefix is already excluded from the agent's own list_files (see tools.py/workspace.py)
and from the chat Files/version UI, but is still git-tracked via commit_snapshot - so these
JSON files survive between turns and are visible in the project's version history without
ever leaking into the agent's ordinary file listings or the chat itself. Never write a
Secret value here - these get read back into review prompts and (as a whole file) are
downloadable from any commit via the existing version-archive endpoint.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from src.services.agent.pipeline_models import (
    PreviewResult,
    ProductBrief,
    ReviewResult,
    UXSpec,
    VisualDirection,
)

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

BRIEF_NAME = "brief.json"
UX_NAME = "ux_spec.json"
VISUAL_NAME = "visual_direction.json"
PREVIEW_NAME = "last_preview.json"
REVIEW_NAME = "last_review.json"


def planning_dir(root: Path) -> Path:
    return root / ".airuntime" / "planning"


def save_model(root: Path, name: str, model: BaseModel) -> Path:
    target_dir = planning_dir(root)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / name
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_model(root: Path, name: str, model_type: type[ModelT]) -> ModelT | None:
    path = planning_dir(root) / name
    if not path.is_file():
        return None
    try:
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        logger.warning("Could not load planning artifact %s: %s", path, exc)
        return None


def save_brief(root: Path, brief: ProductBrief) -> Path:
    return save_model(root, BRIEF_NAME, brief)


def load_brief(root: Path) -> ProductBrief | None:
    return load_model(root, BRIEF_NAME, ProductBrief)


def save_ux(root: Path, ux: UXSpec) -> Path:
    return save_model(root, UX_NAME, ux)


def load_ux(root: Path) -> UXSpec | None:
    return load_model(root, UX_NAME, UXSpec)


def save_visual(root: Path, visual: VisualDirection) -> Path:
    return save_model(root, VISUAL_NAME, visual)


def load_visual(root: Path) -> VisualDirection | None:
    return load_model(root, VISUAL_NAME, VisualDirection)


def save_preview(root: Path, preview: PreviewResult) -> Path:
    return save_model(root, PREVIEW_NAME, preview)


def load_preview(root: Path) -> PreviewResult | None:
    return load_model(root, PREVIEW_NAME, PreviewResult)


def save_review(root: Path, review: ReviewResult) -> Path:
    return save_model(root, REVIEW_NAME, review)


def load_review(root: Path) -> ReviewResult | None:
    return load_model(root, REVIEW_NAME, ReviewResult)


def compose_planning_context(
    *, brief: ProductBrief | None, ux: UXSpec | None, visual: VisualDirection | None
) -> str:
    """Internal context appended to the coding agent's system prompt for the implementation
    step - never shown to the user as-is (prompt.py's own rules already tell the agent not to
    dump raw JSON into chat)."""
    parts = [
        "Внутренние артефакты проектирования этого хода (НЕ показывай пользователю как JSON, "
        "используй как обязательные продуктовые ограничения при реализации):"
    ]
    if brief is not None:
        parts.append(f"\n### ProductBrief\n{brief.model_dump_json(indent=2)}")
    if ux is not None:
        parts.append(f"\n### UX specification\n{ux.model_dump_json(indent=2)}")
    if visual is not None:
        parts.append(f"\n### Visual direction\n{visual.model_dump_json(indent=2)}")
    if len(parts) == 1:
        return ""
    return "\n".join(parts)
