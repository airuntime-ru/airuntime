from typing import Literal

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

    # Billing conversion used to turn the provider's USD token price into platform credits.
    # One ruble equals 100 credits (the same ratio used by top-ups); the FX rate is explicit so
    # operators can update it without a code deploy while historical ledger amounts stay fixed.
    billing_credits_per_rub: int = 100
    billing_usd_to_rub: int = 100
    provider_name: str = "openai"
    openai_api_key: str | None = None
    # When set, Codex CLI talks to this OpenAI-compatible Responses endpoint instead of
    # api.openai.com (login is skipped; auth is a Bearer token from OPENAI_API_KEY).
    openai_base_url: str | None = "https://routerai.ru/api/v1"
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    # Quality-first coding defaults. Cost/latency are deliberately secondary for the primary
    # OpenAI path; gpt-5.6-sol is the current frontier model for complex coding work.
    default_model_openai: str = "gpt-5.6-sol"
    default_model_anthropic: str = "claude-sonnet-5"
    default_model_gemini: str = "gemini-2.5-pro"
    default_model_openrouter: str = "openai/gpt-5.6-sol"

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
    smtp_from_name: str = "AIRuntime"
    smtp_reply_to: str | None = None
    smtp_use_tls: bool = True
    support_email: str | None = "support@airuntime.ru"

    # Codex CLI runner (replaces direct provider HTTP calls for the "openai" path - see
    # backend/src/services/agent/codex_runtime.py). Other providers keep the old HTTP path.
    # A fresh, single-purpose container per turn (see codex_worker.py) built from this image -
    # not a long-lived named container anymore, so codex_container_name is gone.
    codex_image: str = "airuntime-codex"
    # A real coding turn (write/fix a multi-file project, rebuild until it passes) can
    # legitimately run long - give it room to work without getting cut off mid-task.
    codex_turn_timeout_seconds: int = 1800
    # Planning/review calls also use the frontier model at maximum reasoning effort. A 45-second
    # timeout made that quality setting self-defeating on harder prompts, so allow five minutes.
    codex_simple_timeout_seconds: int = 300
    codex_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "max"
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

    # Persistent orchestration engine (backend/src/services/orchestration/) - the only chat-turn
    # path (backend/src/api/routers/chat.py always uses it; the pre-engine event_source()/
    # run_product_pipeline path was removed once the engine covered its required-files/
    # deploy-gate safety net too - see chat.py's _orchestration_event_source). Every capability
    # tier (specialist agents, skills, MCP, worktree isolation, replanning) always runs; there
    # are no on/off switches left for any of them. OrchestrationRun/Plan/AgentTask rows are
    # always persisted to Postgres - that's what makes a run survive a restart, not optional
    # infrastructure to gate.

    orchestration_run_lease_ttl_seconds: int = 180
    orchestration_task_default_timeout_seconds: int = 1800
    # Safety ceiling on how many nodes one plan graph may contain - mirrors the old
    # orchestrator.py's _MAX_SUBTASKS=4 in spirit but larger, since this plans a real DAG
    # (independent read-only + isolated-write parallelism) rather than N sequential text
    # chunks against one shared workspace.
    orchestration_max_plan_tasks: int = 16
    # Loop-detection ceiling (failure_policy.py) - a run that would need more replans than this
    # to converge stops and asks the user instead of grinding forever.
    orchestration_max_replans: int = 3
    orchestration_max_task_attempts: int = 3
    # None = no per-run cap beyond the user's own credit balance (billing.py still gates that).
    orchestration_default_credit_budget: int | None = None
    orchestration_event_backlog_limit: int = 2000
    # Dedicated per-turn Playwright container image (deployment/preview/Dockerfile), built the
    # same way as codex_image (`docker compose build preview`, profiles: [build-only]). Kept out
    # of backend/worker's own Dockerfile so neither image carries browser weight.
    preview_image: str = "airuntime-preview"
    preview_timeout_seconds: int = 90
    preview_memory_limit: str = "1g"
    preview_cpu_limit: str = "1.0"

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

    @field_validator("s3_endpoint_url", "s3_public_endpoint_url", "openai_base_url", mode="before")
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
OPENAI_MODEL_FLOOR = "gpt-5.6-sol"

# Ranked allowlists for auto-select when admin has no preferred_models list.
# Newest / strongest coding-capable models first. This is intentionally quality-first.
CURATED_TOP_MODELS: dict[str, list[str]] = {
    "openai": [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
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
        "openai/gpt-5.6-sol",
        "openai/gpt-5.6-terra",
        "openai/gpt-5.6-luna",
        "anthropic/claude-sonnet-5",
        "google/gemini-2.5-pro",
    ],
}
