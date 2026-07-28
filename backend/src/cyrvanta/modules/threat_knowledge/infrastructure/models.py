from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from cyrvanta.shared.database import Base


class AttackReleaseModel(Base):
    __tablename__ = "attack_releases"
    __table_args__ = (UniqueConstraint("domain", "version", name="uq_attack_release_version"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    domain: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    stix_version: Mapped[str] = mapped_column(String(16), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    bundle_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AttackObjectModel(Base):
    __tablename__ = "attack_objects"
    __table_args__ = (UniqueConstraint("release_id", "stix_id", name="uq_attack_object_stix"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    release_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("attack_releases.id"))
    stix_id: Mapped[str] = mapped_column(String(160), nullable=False)
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(40))
    name_en: Mapped[str | None] = mapped_column(String(500))
    description_en: Mapped[str | None] = mapped_column(Text)
    is_subtechnique: Mapped[bool] = mapped_column(Boolean, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    deprecated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tactic_codes: Mapped[list[str]] = mapped_column(ARRAY(String(80)), nullable=False)
    modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AttackRelationshipModel(Base):
    __tablename__ = "attack_relationships"
    __table_args__ = (
        UniqueConstraint("release_id", "stix_id", name="uq_attack_relationship_stix"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    release_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("attack_releases.id"))
    stix_id: Mapped[str] = mapped_column(String(160), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_stix_id: Mapped[str] = mapped_column(String(160), nullable=False)
    target_stix_id: Mapped[str] = mapped_column(String(160), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ThreatMappingRuleModel(Base):
    __tablename__ = "threat_mapping_rule_versions"
    __table_args__ = (
        UniqueConstraint("rule_code", "version", name="uq_threat_mapping_rule_version"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    rule_code: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    definition: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    definition_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IncidentAttackMappingModel(Base):
    __tablename__ = "incident_attack_mappings"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_incident_attack_mapping_id_tenant"),
        UniqueConstraint("tenant_id", "fingerprint", name="uq_incident_attack_mapping_fingerprint"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    incident_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attack_object_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("attack_objects.id")
    )
    mapping_rule_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("threat_mapping_rule_versions.id")
    )
    correlation_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    selector_codes: Mapped[list[str]] = mapped_column(ARRAY(String(120)), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AttackMappingEvidenceModel(Base):
    __tablename__ = "attack_mapping_evidence"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    mapping_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False)
    finding_revision_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    correlation_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    claim_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    timeline_entry_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class RiskDefinitionModel(Base):
    __tablename__ = "risk_definition_versions"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_risk_definition_version"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    definition: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    definition_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskAssessmentModel(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_risk_assessment_id_tenant"),
        UniqueConstraint(
            "tenant_id", "incident_id", "fingerprint", name="uq_risk_assessment_fingerprint"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    incident_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    definition_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("risk_definition_versions.id")
    )
    correlation_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    band: Mapped[str] = mapped_column(String(16), nullable=False)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskFactorModel(Base):
    __tablename__ = "risk_assessment_factors"
    __table_args__ = (
        UniqueConstraint("tenant_id", "assessment_id", "factor_code", name="uq_risk_factor_code"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    assessment_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    factor_code: Mapped[str] = mapped_column(String(120), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    contribution: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class IncidentExplanationModel(Base):
    __tablename__ = "incident_explanations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "risk_assessment_id", "locale", "mode", name="uq_incident_explanation"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    incident_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    risk_assessment_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    locale: Mapped[str] = mapped_column(String(5), nullable=False)
    mode: Mapped[str] = mapped_column(String(24), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    grounded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
