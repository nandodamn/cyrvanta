from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CorrelationMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    finding_id: UUID
    revision_id: UUID
    role: str
    selector_code: str
    effective_at: datetime
    source_system: str
    is_simulated: bool


class CorrelationFactorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    factor_code: str
    matched: bool
    weight: int
    contribution: int
    explanation_code: str


class CorrelationResponse(BaseModel):
    id: UUID
    incident_id: UUID
    rule_code: str
    rule_version: str
    score: int
    threshold: int
    result_type: str
    explanation: str
    is_simulated: bool
    window_start: datetime | None
    window_end: datetime | None
    claim_id: UUID | None
    created_at: datetime
    members: list[CorrelationMemberResponse] = Field(default_factory=list)
    factors: list[CorrelationFactorResponse] = Field(default_factory=list)
