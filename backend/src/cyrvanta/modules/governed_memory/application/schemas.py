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
    actor_user_id: UUID
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
    created_by_user_id: UUID
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
    matched: bool
    explanation: str


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
