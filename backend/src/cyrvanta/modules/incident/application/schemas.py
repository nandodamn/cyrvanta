from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["informational", "low", "medium", "high", "critical"]
IncidentStatus = Literal[
    "new", "triaged", "investigating", "contained", "resolved", "closed", "reopened"
]


TriageStatus = Literal["UNREVIEWED", "RELEVANT", "DISCARDED"]


class AlertTriageUpdate(BaseModel):
    triage_status: TriageStatus


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source: str
    external_id: str
    observed_at: datetime
    title: str
    category: str
    severity: str
    asset_summary: str | None
    identity_summary: str | None
    indicator_summary: str | None
    provenance: str
    is_simulated: bool
    triage_status: str = "UNREVIEWED"
    reviewed_by_user_id: UUID | None = None
    reviewed_at: datetime | None = None
    reviewer_display_name: str | None = None


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=3, max_length=5000)
    severity: Severity
    priority: int = Field(ge=1, le=5)
    classification: str = Field(min_length=2, max_length=120)


class IncidentUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=3, max_length=300)
    description: str | None = Field(default=None, min_length=3, max_length=5000)
    severity: Severity | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    classification: str | None = Field(default=None, min_length=2, max_length=120)


class IncidentTransition(BaseModel):
    expected_version: int = Field(ge=1)
    target_status: IncidentStatus
    reason: str | None = Field(default=None, min_length=3, max_length=1000)
    close_reason: (
        Literal["false_positive", "duplicate", "accepted_risk", "resolved", "other"] | None
    ) = None


class IncidentAssign(BaseModel):
    expected_version: int = Field(ge=1)
    assignee_user_id: UUID | None


class TimelineCreate(BaseModel):
    expected_version: int = Field(ge=1)
    summary: str = Field(min_length=1, max_length=5000)


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    title: str
    description: str
    status: str
    severity: str
    priority: int
    classification: str
    assignee_user_id: UUID | None
    version: int
    is_simulated: bool
    detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    close_reason: str | None


class TimelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor_user_id: UUID | None
    entry_type: str
    summary: str
    resource_type: str | None
    resource_id: UUID | None
    incident_version: int
    effective_at: datetime
    recorded_at: datetime


class DemoScenarioResponse(BaseModel):
    scenario: str
    incident: IncidentResponse
    alerts_created: int
    idempotent_replay: bool
