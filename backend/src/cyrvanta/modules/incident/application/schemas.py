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


class CollaboratorAdd(BaseModel):
    """Bringing someone into a case without handing it over."""

    user_id: UUID
    reason: str | None = Field(default=None, max_length=500)


class CollaboratorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: UUID
    email: str
    display_name: str
    reason: str | None = None
    added_at: datetime


class HistoryEntry(BaseModel):
    """One line of the incident's record.

    Shaped for reading rather than for storage: an auditor asks who did what,
    when, from which value, to which, and why -- so the row carries all of it,
    including what the actor was to this incident at that moment.
    """

    occurred_at: datetime
    actor_email: str | None
    actor_name: str | None
    # Held at the time, not looked up now. Roles change and assignments move,
    # so resolving them at read time would answer with today's arrangement.
    actor_roles: list[str] = Field(default_factory=list)
    actor_relation: str | None = None
    action: str
    before: dict[str, str] = Field(default_factory=dict)
    after: dict[str, str] = Field(default_factory=dict)
    reason: str | None = None
    source: str


class IncidentAlertsLink(BaseModel):
    """Alerts an analyst is attaching as evidence for an incident.

    `expected_version` is required for the same reason every other mutation
    requires it: two analysts working the same incident must not overwrite each
    other silently. Attaching evidence changes what the incident claims to be
    based on, so it is a mutation like any other.
    """

    expected_version: int = Field(ge=1)
    alert_ids: list[UUID] = Field(min_length=1, max_length=50)


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
