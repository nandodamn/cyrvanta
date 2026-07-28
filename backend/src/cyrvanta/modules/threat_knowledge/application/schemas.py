from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AttackTechniqueResponse(BaseModel):
    id: UUID
    release_version: str
    external_id: str
    name_en: str
    tactic_codes: list[str]
    is_subtechnique: bool
    revoked: bool
    deprecated: bool


class ThreatMappingResponse(BaseModel):
    id: UUID
    incident_id: UUID
    correlation_run_id: UUID
    external_id: str
    name_en: str
    tactic_codes: list[str]
    status: str
    selector_codes: list[str]
    evidence_revision_ids: list[UUID]
    created_at: datetime


class RiskFactorResponse(BaseModel):
    code: str
    weight: int = Field(ge=0, le=100)
    contribution: int = Field(ge=0, le=100)


class RiskAssessmentResponse(BaseModel):
    id: UUID
    incident_id: UUID
    definition_code: str
    definition_version: str
    score: int = Field(ge=0, le=100)
    band: str
    fingerprint: str
    factors: list[RiskFactorResponse]
    created_at: datetime


class ExplanationResponse(BaseModel):
    id: UUID
    incident_id: UUID
    risk_assessment_id: UUID
    locale: str
    mode: str
    provider: str
    text: str
    grounded: bool
    created_at: datetime


class EnrichmentResponse(BaseModel):
    mappings: list[ThreatMappingResponse]
    risk: RiskAssessmentResponse
    explanations: list[ExplanationResponse]
