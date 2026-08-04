from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from cyrvanta.shared.database import Base


class PlaybookDefinitionModel(Base):
    __tablename__ = "playbook_definitions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    name_es: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    description_es: Mapped[str | None] = mapped_column(String(2000))
    description_en: Mapped[str | None] = mapped_column(String(2000))
    action_type: Mapped[str] = mapped_column(String(120), nullable=False)
    approval_mode: Mapped[str | None] = mapped_column(String(32), default="AUTOMATIC", server_default="AUTOMATIC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlaybookVersionModel(Base):
    __tablename__ = "playbook_versions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    definition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    impact: Mapped[str] = mapped_column(String(20), nullable=False)
    classification: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    workflow_code: Mapped[str] = mapped_column(String(120), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    portable_artifact: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    portable_schema_version: Mapped[str | None] = mapped_column(String(16))
    validated_sha256: Mapped[str | None] = mapped_column(String(64))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validated_by_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    input_schema: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    result_schema: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    registered_by_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    approved_by_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AutomationEngineBindingModel(Base):
    __tablename__ = "automation_engine_bindings"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    playbook_version_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    engine_type: Mapped[str] = mapped_column(String(32), nullable=False)
    instance_code: Mapped[str] = mapped_column(String(120), nullable=False)
    adapter_workflow_id: Mapped[str | None] = mapped_column(String(160))
    webhook_path: Mapped[str | None] = mapped_column(String(200))
    key_id: Mapped[str | None] = mapped_column(String(120))
    desired_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_digest: Mapped[str | None] = mapped_column(String(64))
    sync_status: Mapped[str] = mapped_column(String(24), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlaybookExecutionModel(Base):
    __tablename__ = "playbook_executions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    authorization_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_event_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    proposal_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    incident_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    playbook_version_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    binding_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    proposal_fingerprint: Mapped[str | None] = mapped_column(String(64))
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    inputs: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(80))
    adapter_execution_id: Mapped[str | None] = mapped_column(String(200))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlaybookExecutionAttemptModel(Base):
    __tablename__ = "playbook_execution_attempts"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    execution_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    dispatch_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlaybookExecutionAttemptOutcomeModel(Base):
    __tablename__ = "playbook_execution_attempt_outcomes"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    attempt_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlaybookExecutionUpdateModel(Base):
    __tablename__ = "playbook_execution_updates"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    execution_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    adapter_event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_detail: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AutomationReplayNonceModel(Base):
    __tablename__ = "automation_replay_nonces"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    binding_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    key_id: Mapped[str | None] = mapped_column(String(120))
    nonce: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    body_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlaybookStepExecutionModel(Base):
    __tablename__ = "playbook_step_executions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    execution_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    step_id: Mapped[str] = mapped_column(String(64), nullable=False)
    step_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action_code: Mapped[str | None] = mapped_column(String(96))
    action_version: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(80))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlaybookStepAttemptModel(Base):
    __tablename__ = "playbook_step_attempts"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    step_execution_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlaybookStepAttemptOutcomeModel(Base):
    __tablename__ = "playbook_step_attempt_outcomes"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    attempt_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    outcome_event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    result: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    result_sha256: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_detail: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NativeActionBindingModel(Base):
    __tablename__ = "native_action_bindings"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    action_code: Mapped[str] = mapped_column(String(96), nullable=False)
    action_version: Mapped[str] = mapped_column(String(80), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(32), nullable=False)
    credential_key_id: Mapped[str | None] = mapped_column(String(120))
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    configuration_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
