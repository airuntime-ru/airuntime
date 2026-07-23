from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AIRuntime API"
    api_prefix: str = "/api/v1"
    debug: bool = False
    environment: str = "development"
    # Console log verbosity for both the API and worker processes (see core/logging_setup.py).
    log_level: str = "INFO"

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@postgres:5432/airuntime"
    )
    redis_url: str = "redis://redis:6379/0"

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    otp_expire_minutes: int = 10
    app_encryption_key: str | None = None

    default_user_credits: int = 1_000_000_000
    provider_name: str = "openai"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    # Mid-tier+ coding defaults (never weaker than gpt-5.4-mini on OpenAI).
    default_model_openai: str = "gpt-5.4-mini"
    default_model_anthropic: str = "claude-sonnet-5"
    default_model_gemini: str = "gemini-2.5-pro"
    default_model_openrouter: str = "openai/gpt-5.4-mini"

    app_domain: str = "airuntime.ru"
    frontend_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"

    public_base_domain: str | None = None
    allowed_origins: str = "http://localhost:3000"
    allowed_hosts: str = "localhost,127.0.0.1"

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@airuntime.ru"
    smtp_use_tls: bool = True

    # Codex CLI runner (replaces direct provider HTTP calls for the "openai" path - see
    # backend/src/services/agent/codex_runtime.py). Other providers keep the old HTTP path.
    # A fresh, single-purpose container per turn (see codex_worker.py) built from this image -
    # not a long-lived named container anymore, so codex_container_name is gone.
    codex_image: str = "airuntime-codex"
    # A real coding turn (write/fix a multi-file project, rebuild until it passes) can
    # legitimately run long - give it room to work without getting cut off mid-task.
    codex_turn_timeout_seconds: int = 1800
    codex_simple_timeout_seconds: int = 45
    codex_memory_limit: str = "2g"
    codex_cpu_limit: str = "2.0"
    # Docker network the per-turn Codex container joins - needed so it can resolve
    # docker-socket-proxy by name when codex_docker_host is set. Compose's default network name
    # for this project is "airuntime_default" (<compose project name>_default); override via env
    # if deployed under a different COMPOSE_PROJECT_NAME / -p.
    codex_network: str | None = "airuntime_default"
    # docker-socket-proxy address (e.g. "tcp://docker-socket-proxy:2375") for the per-turn
    # container's own docker build/run calls. None (default) keeps the pre-isolation behavior of
    # bind-mounting the raw host socket into it - opt in once the proxy service is deployed (see
    # docker-compose.yml's docker-socket-proxy service).
    codex_docker_host: str | None = None
    # Real host path of the named volume backing generated_projects_dir, looked up via the
    # Docker API at run time (see codex_worker.py's _resolve_project_mount) so a per-turn
    # container can bind-mount just one project's subtree instead of the whole shared volume.
    # Compose prefixes volume names with the project name ("airuntime" from this file's `name:`
    # key) - verify against `docker volume ls` on the target host if COMPOSE_PROJECT_NAME differs.
    generated_projects_volume_name: str = "airuntime_airruntime_projects_data"

    # Off by default - see backend/src/services/agent/orchestrator.py's module docstring for why
    # this is the least-tested piece of the 2026-07-17 architecture work (no live model run to
    # validate the planning call's output against) and docs/architecture.md for the design.
    enable_agent_orchestrator: bool = False

    # Periodic sweep of ad-hoc images Codex builds on its own while self-testing a turn (see
    # image_janitor.py for the safety checks). On by default - flip off if you'd rather review
    # `docker images` and clean up manually.
    image_janitor_enabled: bool = True

    docker_binary: str = "docker"
    deployment_port_base: int = 18000
    deployment_memory_limit: str = "512m"
    deployment_cpu_limit: str = "1.0"
    deployment_timeout_seconds: int = 120
    deployment_default_image: str = "nginx:alpine"
    # Persist generated project sources so they survive container restarts.
    generated_projects_dir: str = "/data/airruntime-projects"
    # Host directory for project sidecar data (Postgres/Redis/…). Bind-mounted into
    # service containers so rebuild/redeploy keeps data. Env: DEPLOYMENT_VOLUMES_DIR
    # (also accepts AIRUNTIME_VOLUMES_DIR). Default is durable on the server, not /tmp.
    deployment_volumes_dir: str = "/var/lib/airuntime/volumes"
    auto_deploy_websites: bool = True
    max_running_projects_per_user: int = 3
    deployment_public_network: str | None = None
    deployment_expose_host_ports: bool = True
    deployment_service_memory_limit: str = "256m"
    deployment_service_cpu_limit: str = "0.5"
    max_services_per_project: int = 100

    cf_zone_id: str | None = None
    cf_api_token: str | None = None
    server_ip: str | None = None

    s3_endpoint_url: str | None = "http://minio:9000"
    s3_public_endpoint_url: str | None = "http://localhost:9000"
    s3_access_key: str = "airuntime"
    s3_secret_key: str = "airuntime-secret"
    s3_bucket: str = "airuntime-files"
    s3_region: str = "us-east-1"
    s3_max_upload_bytes: int = 10 * 1024 * 1024
    s3_presign_expire_seconds: int = 3600

    @field_validator("s3_endpoint_url", "s3_public_endpoint_url", mode="before")
    @classmethod
    def empty_endpoint_to_none(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return value

    @property
    def resolved_app_domain(self) -> str:
        return self.public_base_domain or self.app_domain

    @property
    def resolved_frontend_url(self) -> str:
        return self.frontend_url

    @property
    def resolved_api_url(self) -> str:
        return self.api_url

    def build_project_url(self, subdomain: str) -> str:
        return f"https://{subdomain}.{self.resolved_app_domain}"

    @property
    def allowed_origins_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
        if self.resolved_frontend_url not in origins:
            origins.append(self.resolved_frontend_url)
        return origins

    @property
    def allowed_hosts_list(self) -> list[str]:
        hosts = [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]
        hosts.append(self.resolved_app_domain)
        return list(dict.fromkeys(hosts))

    def validate_production(self) -> None:
        if self.environment != "production":
            return
        weak = {"change-me", "change-me-in-production", "test-secret"}
        if self.jwt_secret_key in weak:
            raise RuntimeError("JWT_SECRET_KEY must be set for production")
        if not self.app_encryption_key:
            raise RuntimeError("APP_ENCRYPTION_KEY must be set for production")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
settings.validate_production()

# OpenAI auto-select floor (product / API slug).
OPENAI_MODEL_FLOOR = "gpt-5.4-mini"

# Ranked allowlists for auto-select when admin has no preferred_models list.
# Newest / strongest coding-capable models first; keep cost/latency reasonable
# (Sonnet over Opus, mini over full frontier as the practical default band).
CURATED_TOP_MODELS: dict[str, list[str]] = {
    "openai": [
        "gpt-5.4-mini",
        "gpt-5.4",
    ],
    "anthropic": [
        "claude-sonnet-5",
        "claude-opus-4-8",
    ],
    "gemini": [
        "gemini-2.5-pro",
        "gemini-3.1-pro-preview",
        "gemini-3.5-flash",
    ],
    "openrouter": [
        "openai/gpt-5.4-mini",
        "openai/gpt-5.4",
        "anthropic/claude-sonnet-5",
        "google/gemini-2.5-pro",
    ],
}
