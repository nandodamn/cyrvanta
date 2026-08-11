from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from cyrvanta.modules.playbooks.application.portable import (
    LocalizedDescription,
    LocalizedTitle,
    PortablePlaybookV1,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DefinitionCreate(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9-]{0,119}$")
    title_i18n: LocalizedTitle
    description_i18n: LocalizedDescription


class DefinitionResponse(StrictModel):
    id: UUID
    code: str
    title_i18n: LocalizedTitle
    description_i18n: LocalizedDescription
    created_at: datetime
    latest_version: str | None = None
    publication_status: str | None = None
    engine_type: Literal["NATIVE", "N8N"] | None = None
    binding_status: str | None = None
    binding_active: bool = False
    execution_mode: Literal["SIMULATED", "LIVE"] | None = None
    impact: str | None = None
    required_parameters: list[str] = Field(default_factory=list)
    credential_aliases: list[str] = Field(default_factory=list)
    target_incident_types: list[str] = Field(default_factory=list)
    mitre_codes: list[str] = Field(default_factory=list)
    rollback_supported: bool = False
    rollback_target_code: str | None = None
    rollback_guidance_i18n: LocalizedDescription | None = None
    automation_policy_i18n: LocalizedDescription | None = None
    approval_mode: Literal["AUTOMATIC", "SINGLE", "FOUR_EYES"] = "AUTOMATIC"
    last_execution_status: str | None = None
    last_executed_at: datetime | None = None


class ToggleBindingPayload(StrictModel):
    active: bool | None = None
    engine_type: Literal["NATIVE", "N8N"] | None = None


class UpdateApprovalGovernancePayload(StrictModel):
    approval_mode: Literal["AUTOMATIC", "SINGLE", "FOUR_EYES"]


class DefinitionList(StrictModel):
    items: list[DefinitionResponse]
    total: int


class VersionCreate(StrictModel):
    artifact: PortablePlaybookV1


class VersionResponse(StrictModel):
    id: UUID
    definition_id: UUID
    version: str
    status: Literal["DRAFT", "PUBLISHED", "RETIRED"]
    engine_mode: Literal["SIMULATED", "LIVE"]
    impact: str
    artifact_sha256: str
    validated_sha256: str | None
    validated_at: datetime | None
    approved_at: datetime | None
    created_at: datetime


class ValidationResponse(StrictModel):
    valid: bool
    digest: str
    error_codes: list[str]


class DryRunCreate(StrictModel):
    inputs: dict[str, object] = Field(default_factory=dict)


class DryRunResponse(StrictModel):
    valid: bool
    engine_type: Literal["NATIVE"]
    steps: list[str]
    error_codes: list[str]


class ActionResponse(StrictModel):
    code: str
    version: str
    modes: list[str]
    impact: str
    timeout_seconds: int
    retry_safe: bool
    cancellable: bool
    egress: str


class ActionList(StrictModel):
    items: list[ActionResponse]
    total: int


class NativeBindingCreate(StrictModel):
    playbook_version_id: UUID
    engine_type: Literal["NATIVE"]
    instance_code: Literal["cyrvanta-native"] = "cyrvanta-native"


class N8nBindingCreate(StrictModel):
    playbook_version_id: UUID
    engine_type: Literal["N8N"]
    instance_code: str = Field(min_length=1, max_length=120)
    adapter_workflow_id: str = Field(min_length=1, max_length=160)
    webhook_path: str = Field(pattern=r"^[A-Za-z0-9/_-]{1,200}$")
    key_id: str = Field(min_length=1, max_length=120)


BindingCreate = Annotated[
    NativeBindingCreate | N8nBindingCreate, Field(discriminator="engine_type")
]


class BindingResponse(StrictModel):
    id: UUID
    playbook_version_id: UUID
    engine_type: Literal["NATIVE", "N8N"]
    instance_code: str
    sync_status: str
    active: bool
    desired_digest: str
    observed_digest: str | None
    last_verified_at: datetime | None
    created_at: datetime


class BindingList(StrictModel):
    items: list[BindingResponse]
    total: int


class NativeActionBindingCreate(StrictModel):
    action_code: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,95}$")
    action_version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
    connector_type: Literal["SIMULATED", "HTTP_ALLOWLISTED"]
    credential_key_id: str | None = Field(default=None, min_length=1, max_length=120)
    configuration: dict[str, object] = Field(default_factory=dict)


class NativeActionBindingResponse(StrictModel):
    id: UUID
    action_code: str
    action_version: str
    connector_type: str
    credential_configured: bool
    configuration_sha256: str
    active: bool
    last_verified_at: datetime | None
    created_at: datetime


class EmptyBody(StrictModel):
    pass
