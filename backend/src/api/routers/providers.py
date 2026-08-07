from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencies.auth import get_current_user
from src.core.config import CURATED_TOP_MODELS, settings
from src.db.models.user import User
from src.db.session import get_db
from src.services.model_access import resolve_model_for_user, visible_models_for_user
from src.services.model_pricing import public_model_options
from src.services.system_settings import resolve_api_key_for_provider

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderConfigResponse(BaseModel):
    active: str
    supported: list[str]
    configured: dict[str, bool]
    auto_provider: str
    auto_model: str
    defaults: dict[str, str]
    top_models: dict[str, list[str]]
    models: dict[str, list[dict]]
    credits_per_rub: int


@router.get("", response_model=ProviderConfigResponse)
def list_providers(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ProviderConfigResponse:
    openai_key = resolve_api_key_for_provider("openai") or settings.openai_api_key
    anthropic_key = resolve_api_key_for_provider("anthropic") or settings.anthropic_api_key
    gemini_key = resolve_api_key_for_provider("gemini") or settings.gemini_api_key
    openrouter_key = resolve_api_key_for_provider("openrouter") or settings.openrouter_api_key
    # Plan-aware: a free account must not be offered (or auto-routed to) the frontier model.
    auto_provider, auto_model = resolve_model_for_user(db, current_user)
    return ProviderConfigResponse(
        active=settings.provider_name,
        supported=["openai", "anthropic", "gemini", "openrouter"],
        configured={
            "openai": bool(openai_key),
            "anthropic": bool(anthropic_key),
            "gemini": bool(gemini_key),
            "openrouter": bool(openrouter_key),
        },
        auto_provider=auto_provider,
        auto_model=auto_model,
        defaults={
            "openai": settings.default_model_openai,
            "anthropic": settings.default_model_anthropic,
            "gemini": settings.default_model_gemini,
            "openrouter": settings.default_model_openrouter,
        },
        top_models={
            provider: [
                str(row["id"])
                for row in visible_models_for_user(
                    db, current_user, public_model_options(provider), provider=provider
                )
            ]
            or CURATED_TOP_MODELS.get(provider, [])
            for provider in ("openai", "anthropic", "gemini", "openrouter")
        },
        models={
            provider: visible_models_for_user(
                db, current_user, public_model_options(provider), provider=provider
            )
            for provider in ("openai", "anthropic", "gemini", "openrouter")
        },
        credits_per_rub=settings.billing_credits_per_rub,
    )
