from agents.provider.adapter import ProviderAdapter
from agents.runtime import AIRuntimeEngine
from src.core.config import settings
from src.services.deployment.docker_adapter import DeployRequest, DockerDeploymentAdapter, slugify
from src.services.memory import recall_chat, remember_chat
from src.services.provider.factory import get_provider, resolve_model


def _deploy_project(*, project_id: str, image_ref: str, subdomain: str) -> dict:
    adapter = DockerDeploymentAdapter()
    return adapter.deploy(
        DeployRequest(project_id=project_id, image_ref=image_ref, subdomain=subdomain)
    )


def _remember(chat_id: str, role: str, content: str) -> None:
    remember_chat(chat_id=chat_id, role=role, content=content)


def _recall(chat_id: str) -> list[dict]:
    return recall_chat(chat_id=chat_id)


_engine: AIRuntimeEngine | None = None


def get_runtime_engine() -> AIRuntimeEngine:
    global _engine
    if _engine is None:
        provider = ProviderAdapter(get_provider(settings.provider_name))

        def deploy_fn(*, project_id: str, image_ref: str, subdomain: str) -> dict:
            safe_subdomain = subdomain or f"{slugify('project')}-{project_id[:8]}"
            return _deploy_project(
                project_id=project_id,
                image_ref=image_ref or settings.deployment_default_image,
                subdomain=safe_subdomain,
            )

        _engine = AIRuntimeEngine(
            provider=provider,
            recall=_recall,
            remember=_remember,
            resolve_model=lambda: resolve_model(settings.provider_name),
            deploy_fn=deploy_fn,
        )
    return _engine
