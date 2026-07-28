import re

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class WazuhConnectorConfigV1(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1"
    manager_host: str = Field(min_length=1, max_length=253)
    manager_port: int = Field(default=1514, ge=1, le=65535)
    indexer_url: AnyHttpUrl
    index_pattern: str = "wazuh-alerts-*"
    verify_tls: bool = True
    api_username_secret_ref: str | None = Field(default=None, max_length=300)
    api_password_secret_ref: str | None = Field(default=None, max_length=300)
    timeout_seconds: float = Field(default=10, ge=1, le=60)
    max_response_bytes: int = Field(default=5_000_000, ge=1024, le=20_000_000)

    @field_validator("manager_host")
    @classmethod
    def validate_manager_host(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9.-]+", value):
            raise ValueError("manager_host must be a hostname or IP address")
        return value

    @field_validator("index_pattern")
    @classmethod
    def validate_index_pattern(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9._*-]+", value) or value.count("*") > 1:
            raise ValueError("index_pattern contains unsupported characters")
        return value
