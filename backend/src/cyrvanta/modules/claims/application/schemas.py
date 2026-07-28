from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ClaimTypeInput = Literal[
    "FACT", "DERIVED_FACT", "INFERENCE", "HYPOTHESIS", "RECOMMENDATION"
]
EvidenceTypeInput = Literal[
    "FINDING_REVISION",
    "ALERT_REFERENCE",
    "INCIDENT",
    "INCIDENT_TIMELINE_ENTRY",
    "AUDIT_EVENT",
    "CLAIM",
]
EvidenceRelationshipInput = Literal["SUPPORTS", "REFUTES", "CONTEXT"]
AssessmentOutcomeInput = Literal[
    "VALIDATED", "REJECTED", "INSUFFICIENT_EVIDENCE", "RETRACTED"
]
ClaimRelationshipInput = Literal[
    "SUPPORTS", "CONTRADICTS", "DERIVED_FROM", "SUPERSEDES", "RESPONDS_TO"
]


class EvidenceInput(BaseModel):
    evidence_type: EvidenceTypeInput
    evidence_id: UUID
    relationship: EvidenceRelationshipInput = "SUPPORTS"
    evidence_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ClaimCreate(BaseModel):
    claim_type: ClaimTypeInput
    statement: str = Field(min_length=1, max_length=2000)
    language_code: Literal["es", "en", "und"]
    confidence: float | None = Field(default=None, ge=0, le=1)
    explanation: str | None = Field(default=None, max_length=4000)
    validation_criteria: str | None = Field(default=None, max_length=2000)
    missing_evidence: list[str] = Field(default_factory=list, max_length=16)
    method_code: str | None = Field(default=None, max_length=120)
    method_version: str | None = Field(default=None, max_length=80)
    evidence: list[EvidenceInput] = Field(min_length=1, max_length=32)


class AssessmentCreate(BaseModel):
    outcome: AssessmentOutcomeInput
    explanation: str = Field(min_length=1, max_length=4000)


class RelationshipCreate(BaseModel):
    target_claim_id: UUID
    relationship_type: ClaimRelationshipInput


class PresentationCreate(BaseModel):
    locale: Literal["es", "en"]
    text: str = Field(min_length=1, max_length=2000)


class EvidenceResponse(BaseModel):
    evidence_type: str
    evidence_id: UUID
    relationship: str
    evidence_sha256: str | None


class ClaimResponse(BaseModel):
    id: UUID
    incident_id: UUID
    claim_type: str
    statement: str
    language_code: str
    confidence: float | None
    origin_type: str
    origin_actor_user_id: UUID | None
    origin_code: str | None
    origin_version: str | None
    provider: str | None
    model: str | None
    explanation: str | None
    validation_criteria: str | None
    missing_evidence: list[str]
    is_simulated: bool
    state: str
    evidence: list[EvidenceResponse]
    presentations: dict[str, str]
    created_at: datetime


class AssessmentResponse(BaseModel):
    id: UUID
    claim_id: UUID
    outcome: str
    evaluator_user_id: UUID | None
    explanation: str
    created_at: datetime


class RelationshipResponse(BaseModel):
    id: UUID
    source_claim_id: UUID
    target_claim_id: UUID
    relationship_type: str
    created_at: datetime


class PresentationResponse(BaseModel):
    id: UUID
    claim_id: UUID
    locale: str
    text: str
    version: int
    created_at: datetime
