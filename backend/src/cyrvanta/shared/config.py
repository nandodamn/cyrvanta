from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    default_locale: str = "es-UY"
    frontend_url: str = "http://localhost"
    cors_origins: str = "http://localhost,http://localhost:5173"
    database_url: str = "postgresql+asyncpg://cyrvanta:change-me@postgres:5432/cyrvanta"
    redis_url: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://cyrvanta:change-me@rabbitmq:5672/"
    event_max_payload_bytes: int = Field(default=262_144, ge=1024, le=1_048_576)
    outbox_batch_size: int = Field(default=50, ge=1, le=500)
    outbox_lease_seconds: int = Field(default=60, ge=1, le=3600)
    outbox_poll_interval_seconds: float = Field(default=1.0, ge=0.1, le=60)
    event_handler_timeout_seconds: int = Field(default=30, ge=1, le=3600)
    event_consumer_prefetch: int = Field(default=16, ge=1, le=500)
    event_retry_delays_seconds: str = "5,30,300"
    jwt_secret: str = Field(min_length=32)
    integration_encryption_key: str = Field(min_length=43, max_length=44)
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    session_cookie_secure: bool | None = None
    opensearch_mode: str = "simulated"
    opensearch_url: str = "http://opensearch:9200"
    opensearch_index_pattern: str = "wazuh-alerts-*"
    wazuh_mode: str = "simulated"
    wazuh_manager_host: str = "wazuh-manager"
    wazuh_manager_port: int = 1514
    ollama_mode: str = "simulated"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "gemma4:e4b"
    ai_request_timeout_seconds: int = 120
    n8n_mode: str = "simulated"
    n8n_base_url: str = "http://n8n:5678"
    n8n_editor_url: str = "http://localhost:5678"
    n8n_api_key: str = ""
    n8n_allowed_workflow_ids: str = "cyrvanta-demo-response"
    automation_kill_switch: bool = False
    directory_demo_enabled: bool = False
    directory_demo_username: str = "ldap-demo"
    directory_demo_password: str = ""

    @property
    def allowed_workflow_ids(self) -> set[str]:
        return {item.strip() for item in self.n8n_allowed_workflow_ids.split(",") if item.strip()}

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def retry_delays_seconds(self) -> tuple[int, ...]:
        values = tuple(
            int(item.strip()) for item in self.event_retry_delays_seconds.split(",") if item.strip()
        )
        if not values or len(values) > 5 or any(value < 1 or value > 3600 for value in values):
            raise ValueError("EVENT_RETRY_DELAYS_SECONDS must contain 1-5 values from 1 to 3600")
        return values

    @property
    def secure_session_cookie(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.environment not in {"development", "test"}


@lru_cache
def get_settings() -> Settings:
    # BaseSettings resolves required values from the environment at runtime.
    return Settings()
