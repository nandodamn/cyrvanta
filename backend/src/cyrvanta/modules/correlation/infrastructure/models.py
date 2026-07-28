from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from cyrvanta.shared.database import Base


class CorrelationRuleVersionModel(Base):
    __tablename__ = "correlation_rule_versions"
    __table_args__ = (UniqueConstraint("rule_code", "version", name="uq_correlation_rule_version"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    rule_code: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    definition: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    definition_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CorrelationMemberModel(Base):
    __tablename__ = "correlation_members"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "correlation_run_id",
            "revision_id",
            name="uq_correlation_member_revision",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    correlation_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("correlation_runs.id"), nullable=False
    )
    finding_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("alert_references.id"), nullable=False
    )
    revision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("finding_revisions.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    selector_code: Mapped[str] = mapped_column(String(120), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    integration_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CorrelationFactorModel(Base):
    __tablename__ = "correlation_factors"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "correlation_run_id",
            "factor_code",
            name="uq_correlation_factor_code",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    correlation_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("correlation_runs.id"), nullable=False
    )
    factor_code: Mapped[str] = mapped_column(String(120), nullable=False)
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    contribution: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_revision_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), nullable=False
    )
    explanation_code: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
