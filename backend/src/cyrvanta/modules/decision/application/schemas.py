from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from cyrvanta.modules.decision.domain.models import ActionImpact, ResponseMode


class ActionProposalCreate(BaseModel):
    incident_id: UUID
    action_type: Literal[
        "contain-and-document-incident",
        "compromised-account",
        "compromised-endpoint",
        "phishing-malicious-email",
        "ransomware-destructive",
        "lateral-movement",
        "malicious-indicator",
        "privilege-escalation",
        "security-control-disabled",
        "automated-enrichment",
        "escalation-notification",
        "evidence-preservation",
        "closure-controlled-learning",
    ]    impact: ActionImpact
    requested_mode: ResponseMode
    workflow_id: str = Field(min_length=1, max_length=120)
    workflow_version: str = Field(min_length=1, max_length=80)
    targets: list[str] = Field(min_length=1, max_length=100)
    parameters: dict[str, object] = Field(default_factory=dict)
    evidence_refs: list[UUID] = Field(default_factory=list, max_length=32)

    @field_validator("targets")
    @classmethod
    def normalize_targets(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if not normalized or any(len(item) > 256 for item in normalized):
            raise ValueError("targets must be non-empty and at most 256 characters")
        return normalized


class ApprovalDecisionCreate(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    reason: str = Field(min_length=1, max_length=1000)
    expected_proposal_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ApprovalDecisionResponse(BaseModel):
    id: UUID
    actor_user_id: UUID
    decision: str
    reason: str
    created_at: datetime


class AuthorizationResponse(BaseModel):
    id: UUID
    status: str
    expires_at: datetime


class ActionProposalResponse(BaseModel):
    id: UUID
    incident_id: UUID
    requester_user_id: UUID
    action_type: str
    impact: str
    requested_mode: str
    workflow_id: str
    workflow_version: str
    targets: list[str]
    parameters: dict[str, object]
    evidence_refs: list[UUID]
    incident_version: int
    is_simulated: bool
    fingerprint: str
    status: str
    evaluation_outcome: str
    reason_codes: list[str]
    approval_request_id: UUID | None
    required_approvals: int
    approval_status: str | None
    approval_expires_at: datetime | None
    decisions: list[ApprovalDecisionResponse]
    authorization: AuthorizationResponse | None
    created_at: datetime


class ActionProposalList(BaseModel):
    items: list[ActionProposalResponse]
    total: int
