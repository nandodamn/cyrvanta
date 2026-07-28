from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from cyrvanta.shared.database import Base


class ClaimModel(Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_claims_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "incident_id",
            "idempotency_key",
            name="uq_claims_idempotency",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    incident_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("incidents.id"))
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    statement: Mapped[str] = mapped_column(String(2000), nullable=False)
    language_code: Mapped[str] = mapped_column(String(3), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    origin_type: Mapped[str] = mapped_column(String(16), nullable=False)
    origin_actor_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id")
    )
    origin_code: Mapped[str | None] = mapped_column(String(120))
    origin_version: Mapped[str | None] = mapped_column(String(80))
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(160))
    prompt_template_version: Mapped[str | None] = mapped_column(String(80))
    output_schema_version: Mapped[str | None] = mapped_column(String(80))
    input_fingerprint: Mapped[str | None] = mapped_column(String(64))
    explanation: Mapped[str | None] = mapped_column(Text)
    validation_criteria: Mapped[str | None] = mapped_column(Text)
    missing_evidence: Mapped[list[str]] = mapped_column(
        ARRAY(String(80)), nullable=False, default=list
    )
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClaimEvidenceLinkModel(Base):
    __tablename__ = "claim_evidence_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "claim_id",
            "evidence_type",
            "evidence_id",
            "relationship",
            name="uq_claim_evidence_link",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("claims.id"))
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    relationship: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_sha256: Mapped[str | None] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id")
    )
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClaimRelationshipModel(Base):
    __tablename__ = "claim_relationships"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source_claim_id",
            "target_claim_id",
            "relationship_type",
            name="uq_claim_relationship",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    source_claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("claims.id"))
    target_claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("claims.id"))
    relationship_type: Mapped[str] = mapped_column(String(24), nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id")
    )
    producer: Mapped[str] = mapped_column(String(120), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClaimAssessmentModel(Base):
    __tablename__ = "claim_assessments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("claims.id"))
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluator_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id")
    )
    evaluator_rule_code: Mapped[str | None] = mapped_column(String(120))
    evaluator_rule_version: Mapped[str | None] = mapped_column(String(80))
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClaimPresentationModel(Base):
    __tablename__ = "claim_presentations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "claim_id",
            "locale",
            "version",
            name="uq_claim_presentation_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("claims.id"))
    locale: Mapped[str] = mapped_column(String(2), nullable=False)
    text: Mapped[str] = mapped_column(String(2000), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    origin_type: Mapped[str] = mapped_column(String(16), nullable=False)
    origin_actor_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id")
    )
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(160))
    correlation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
