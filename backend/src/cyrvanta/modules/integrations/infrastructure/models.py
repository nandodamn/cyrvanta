from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from cyrvanta.shared.database import Base


class IntegrationModel(Base):
    __tablename__ = "integrations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    connector_type: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="disabled")
    configuration_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    configuration_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    capabilities_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IntegrationSyncStateModel(Base):
    __tablename__ = "integration_sync_state"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    integration_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE")
    )
    stream_type: Mapped[str] = mapped_column(String(80), nullable=False)
    cursor: Mapped[str | None] = mapped_column(Text)
    watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="idle")
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class IntegrationHealthHistoryModel(Base):
    __tablename__ = "integration_health_history"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    integration_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message_redacted: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FindingRevisionModel(Base):
    __tablename__ = "finding_revisions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    alert_reference_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("alert_references.id")
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    integration_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    source_instance_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_object_id: Mapped[str] = mapped_column(String(512), nullable=False)
    source_occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_time_basis: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    severity_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    category: Mapped[str | None] = mapped_column(String(120))
    external_status: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_reference: Mapped[str | None] = mapped_column(String(200))
    entity_references: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    evidence_locator: Mapped[str] = mapped_column(String(2048), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    fingerprint_version: Mapped[str] = mapped_column(String(20), nullable=False)
    adapter_name: Mapped[str] = mapped_column(String(80), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(40), nullable=False)
    normalizer_version: Mapped[str] = mapped_column(String(40), nullable=False)
    canonical_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    normalization_status: Mapped[str] = mapped_column(String(16), nullable=False)
    completeness_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    issue_codes: Mapped[list[str]] = mapped_column(ARRAY(String(80)), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
