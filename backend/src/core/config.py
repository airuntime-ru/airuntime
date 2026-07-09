from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AIRuntime API"
    api_prefix: str = "/api/v1"
    debug: bool = False
    environment: str = "development"

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
    default_model_openai: str = "gpt-4o-mini"
    default_model_anthropic: str = "claude-3-5-haiku-latest"
    default_model_gemini: str = "gemini-1.5-flash"
    default_model_openrouter: str = "openai/gpt-4o-mini"

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

    docker_binary: str = "docker"
    deployment_port_base: int = 18000
    deployment_memory_limit: str = "512m"
    deployment_cpu_limit: str = "1.0"
    deployment_timeout_seconds: int = 120
    deployment_default_image: str = "nginx:alpine"
    # Persist generated project sources so they survive container restarts.
    generated_projects_dir: str = "/data/airruntime-projects"
    auto_deploy_websites: bool = True
    max_running_projects_per_user: int = 3
    deployment_public_network: str | None = None
    deployment_expose_host_ports: bool = True

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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
settings.validate_production()
