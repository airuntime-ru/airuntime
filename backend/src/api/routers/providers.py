from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.dependencies.auth import get_current_user
from src.core.config import settings
from src.db.models.user import User

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderConfigResponse(BaseModel):
    active: str
    supported: list[str]
    configured: dict[str, bool]


@router.get("", response_model=ProviderConfigResponse)
def list_providers(_: User = Depends(get_current_user)) -> ProviderConfigResponse:
    return ProviderConfigResponse(
        active=settings.provider_name,
        supported=["openai", "anthropic", "gemini", "openrouter"],
        configured={
            "openai": bool(settings.openai_api_key),
            "anthropic": bool(settings.anthropic_api_key),
            "gemini": bool(settings.gemini_api_key),
            "openrouter": bool(settings.openrouter_api_key),
        },
    )
