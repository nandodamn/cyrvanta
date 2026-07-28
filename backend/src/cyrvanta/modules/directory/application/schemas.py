from typing import Literal
from uuid import UUID

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator


class DirectoryConfigurationWrite(BaseModel):
    provider_type: Literal["ldap", "active_directory"]
    server_uri: str
    use_starttls: bool = False
    base_dn: str = Field(min_length=3, max_length=1000)
    bind_dn: str = Field(min_length=3, max_length=1000)
    bind_password: str | None = Field(default=None, min_length=1, max_length=1000)
    user_filter: str = Field(min_length=3, max_length=1000)
    login_attribute: str = Field(min_length=1, max_length=100)
    subject_attribute: str = Field(min_length=1, max_length=100)
    email_attribute: str = Field(min_length=1, max_length=100)
    display_name_attribute: str = Field(min_length=1, max_length=100)
    group_base_dn: str | None = Field(default=None, max_length=1000)
    group_filter: str | None = Field(default=None, max_length=1000)
    group_attribute: str | None = Field(default=None, max_length=100)
    ca_certificate_pem: str | None = Field(default=None, max_length=100_000)
    jit_enabled: bool = False
    timeout_seconds: int = Field(default=5, ge=1, le=30)

    @field_validator("server_uri")
    @classmethod
    def secure_server_uri(cls, value: str) -> str:
        parsed = AnyUrl(value)
        if parsed.scheme not in {"ldap", "ldaps"}:
            raise ValueError("Directory URI must use ldap or ldaps")
        return value

    @field_validator("user_filter")
    @classmethod
    def bounded_user_filter(cls, value: str) -> str:
        if value.count("{username}") != 1:
            raise ValueError("User filter must contain exactly one {username} placeholder")
        return value


class DirectoryConfigurationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    provider_type: str
    status: str
    server_uri: str
    use_starttls: bool
    base_dn: str
    bind_dn: str
    has_bind_secret: bool = True
    user_filter: str
    login_attribute: str
    subject_attribute: str
    email_attribute: str
    display_name_attribute: str
    group_base_dn: str | None
    group_filter: str | None
    group_attribute: str | None
    has_ca_certificate: bool = False
    jit_enabled: bool
    timeout_seconds: int
    last_test_success: bool | None


class DirectoryTestResponse(BaseModel):
    success: bool
    detail_code: str


class DirectoryLoginRequest(BaseModel):
    tenant_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1000)
    remember_me: bool = False


class DirectoryLinkWrite(BaseModel):
    external_subject: str = Field(min_length=1, max_length=1000)
    normalized_username: str = Field(min_length=1, max_length=256)


class DirectoryGroupMappingWrite(BaseModel):
    external_group: str = Field(min_length=1, max_length=1000)
    role_id: UUID


class DirectoryGroupMappingsWrite(BaseModel):
    mappings: list[DirectoryGroupMappingWrite] = Field(max_length=100)


class DirectoryGroupMappingResponse(DirectoryGroupMappingWrite):
    id: UUID
