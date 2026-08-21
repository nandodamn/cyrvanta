from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cyrvanta.modules.governed_memory.domain.models import (
    FeedbackOutcome,
    MemoryKind,
    MemorySourceType,
    ReviewDecision,
)


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FeedbackCreate(StrictBody):
    resource_type: Literal["INCIDENT", "FINDING", "CLAIM", "ACTION_PROPOSAL", "PLAYBOOK_EXECUTION"]
    resource_id: UUID
    outcome: FeedbackOutcome
    reason: str = Field(min_length=1, max_length=1000)
    is_synthetic: Literal[False] = False
    occurred_at: datetime

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason must not be blank")
        return value

    @field_validator("occurred_at")
    @classmethod
    def require_aware_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value


class FeedbackResponse(BaseModel):
    id: UUID
    resource_type: str
    resource_id: UUID
    # What the feedback is about and who wrote it, in words. An entry is chosen
    # later as evidence for a memory candidate, and nobody recognises the case
    # they worked on from a UUID.
    resource_label: str | None = None
    actor_user_id: UUID
    actor_name: str | None = None
    outcome: str
    reason: str
    is_synthetic: bool
    occurred_at: datetime
    created_at: datetime


class FeedbackList(BaseModel):
    items: list[FeedbackResponse]
    total: int


class MemoryCandidateCreate(StrictBody):
    kind: MemoryKind
    source_type: MemorySourceType = MemorySourceType.HUMAN
    title_es: str = Field(min_length=1, max_length=200)
    title_en: str = Field(min_length=1, max_length=200)
    statement_es: str = Field(min_length=1, max_length=2000)
    statement_en: str = Field(min_length=1, max_length=2000)
    conditions: dict[str, object] = Field(default_factory=dict)
    evidence_refs: list[UUID] = Field(min_length=1, max_length=100)
    is_synthetic: Literal[False] = False
    valid_from: datetime
    valid_until: datetime

    @field_validator("title_es", "title_en", "statement_es", "statement_en")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value

    @model_validator(mode="after")
    def valid_window(self) -> "MemoryCandidateCreate":
        if (
            self.valid_from.tzinfo is None
            or self.valid_from.utcoffset() is None
            or self.valid_until.tzinfo is None
            or self.valid_until.utcoffset() is None
        ):
            raise ValueError("memory validity timestamps must be timezone-aware")
        if self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


class MemoryVersionCreate(StrictBody):
    """A correction: the same memory, said again and differently.

    Carries a reason because a new version replaces what a reviewer may have
    already read, and the record has to say why.
    """

    title_es: str = Field(min_length=1, max_length=200)
    title_en: str = Field(min_length=1, max_length=200)
    statement_es: str = Field(min_length=1, max_length=2000)
    statement_en: str = Field(min_length=1, max_length=2000)
    conditions: dict[str, object] = Field(default_factory=dict)
    evidence_refs: list[UUID] = Field(min_length=1, max_length=100)
    valid_from: datetime
    valid_until: datetime
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("title_es", "title_en", "statement_es", "statement_en", "reason")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value

    @model_validator(mode="after")
    def valid_window(self) -> "MemoryVersionCreate":
        if (
            self.valid_from.tzinfo is None
            or self.valid_from.utcoffset() is None
            or self.valid_until.tzinfo is None
            or self.valid_until.utcoffset() is None
        ):
            raise ValueError("memory validity timestamps must be timezone-aware")
        if self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


class MemoryReviewCreate(StrictBody):
    decision: ReviewDecision
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason must not be blank")
        return value


class MemoryReason(StrictBody):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason must not be blank")
        return value


class MemoryReviewResponse(BaseModel):
    id: UUID
    reviewer_user_id: UUID
    decision: str
    reason: str
    created_at: datetime


class MemoryStateResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    from_status: str | None
    to_status: str
    reason: str
    occurred_at: datetime


class MemoryCandidateResponse(BaseModel):
    id: UUID
    version_id: UUID
    version: int
    kind: str
    source_type: str
    # Null when the AI drafted it: there is no human author, which is why any
    # analyst may review it.
    created_by_user_id: UUID | None = None
    # The author of *this* version, which after a correction is not always the
    # author of the candidate. It is what the separation rules read, so it is
    # what the screen has to show.
    version_author_user_id: UUID | None = None
    version_author_name: str | None = None
    title_es: str
    title_en: str
    statement_es: str
    statement_en: str
    conditions: dict[str, object]
    evidence_refs: list[UUID]
    is_synthetic: bool
    valid_from: datetime
    valid_until: datetime
    status: str
    reviews: list[MemoryReviewResponse]
    state_history: list[MemoryStateResponse]
    created_at: datetime


class MemoryCandidateList(BaseModel):
    items: list[MemoryCandidateResponse]
    total: int


class MemoryContextEvaluate(StrictBody):
    consumer_type: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9_]+$")
    consumer_id: UUID
    base_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    context: dict[str, object] = Field(default_factory=dict)


class MemoryMatchResponse(BaseModel):
    version_id: UUID
    version: int
    # Carried with the match so a reader sees the lesson itself, not a UUID
    # plus an invitation to go and look it up somewhere else.
    title_es: str
    title_en: str
    statement_es: str
    statement_en: str
    valid_until: datetime
    matched: bool
    explanation: str


class MemoryInfluenceStatus(BaseModel):
    """Whether this installation consults memory, not what the default is."""

    enabled: bool


class MemoryContextResponse(BaseModel):
    influence_enabled: bool
    base_fingerprint: str
    presented_fingerprint: str
    matches: list[MemoryMatchResponse]


class MemoryMetricResponse(BaseModel):
    id: UUID
    code: str
    version: int
    window_start: datetime
    window_end: datetime
    sample_size: int
    numerator: int
    denominator: int
    value: Decimal
    sufficient_sample: bool
    input_fingerprint: str


class MemoryMetricList(BaseModel):
    items: list[MemoryMetricResponse]
    total: int
