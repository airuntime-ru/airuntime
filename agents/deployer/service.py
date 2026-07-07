from collections.abc import Callable


class DeployerService:
    def __init__(self, *, deploy_fn: Callable[..., dict]) -> None:
        self._deploy_fn = deploy_fn

    def deploy(self, *, project_id: str, artifact_ref: str, config: dict) -> dict:
        return self._deploy_fn(
            project_id=project_id,
            image_ref=artifact_ref,
            subdomain=config.get("subdomain", f"project-{project_id[:8]}"),
        )
