from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class ClaimType(StrEnum):
    FACT = "FACT"
    DERIVED_FACT = "DERIVED_FACT"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    RECOMMENDATION = "RECOMMENDATION"
    DECISION = "DECISION"
    ACTION = "ACTION"
    RESULT = "RESULT"


class ClaimOriginType(StrEnum):
    SOURCE = "SOURCE"
    HUMAN = "HUMAN"
    RULE = "RULE"
    SYSTEM = "SYSTEM"
    AI = "AI"


class EvidenceType(StrEnum):
    FINDING_REVISION = "FINDING_REVISION"
    ALERT_REFERENCE = "ALERT_REFERENCE"
    INCIDENT = "INCIDENT"
    INCIDENT_TIMELINE_ENTRY = "INCIDENT_TIMELINE_ENTRY"
    AUDIT_EVENT = "AUDIT_EVENT"
    CLAIM = "CLAIM"


class EvidenceRelationship(StrEnum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    CONTEXT = "CONTEXT"


class ClaimRelationshipType(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    DERIVED_FROM = "DERIVED_FROM"
    SUPERSEDES = "SUPERSEDES"
    RESPONDS_TO = "RESPONDS_TO"


class AssessmentOutcome(StrEnum):
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    RETRACTED = "RETRACTED"


class ClaimPresentationState(StrEnum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONTESTED = "CONTESTED"
    SUPERSEDED = "SUPERSEDED"
    RETRACTED = "RETRACTED"


IMPLEMENTED_CLAIM_TYPES = frozenset(
    {
        ClaimType.FACT,
        ClaimType.DERIVED_FACT,
        ClaimType.INFERENCE,
        ClaimType.HYPOTHESIS,
        ClaimType.RECOMMENDATION,
    }
)
NON_DETERMINISTIC_TYPES = frozenset(
    {ClaimType.INFERENCE, ClaimType.HYPOTHESIS, ClaimType.RECOMMENDATION}
)
AI_PROHIBITED_TYPES = frozenset(
    {ClaimType.FACT, ClaimType.DECISION, ClaimType.ACTION, ClaimType.RESULT}
)
MISSING_EVIDENCE_CODE = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class Claim:
    claim_id: UUID
    tenant_id: UUID
    incident_id: UUID
    claim_type: ClaimType
    statement: str
    language_code: str
    confidence: float | None
    origin_type: ClaimOriginType
    origin_actor_user_id: UUID | None
    origin_code: str | None
    origin_version: str | None
    provider: str | None
    model: str | None
    prompt_template_version: str | None
    output_schema_version: str | None
    input_fingerprint: str | None
    explanation: str | None
    validation_criteria: str | None
    missing_evidence: tuple[str, ...]
    is_simulated: bool
    correlation_id: UUID
    causation_id: UUID | None
    created_at: datetime
    idempotency_key: str | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", _utc(self.created_at))
        if self.claim_type not in IMPLEMENTED_CLAIM_TYPES:
            raise ValueError("claim type is reserved for a later stage")
        if not self.statement.strip() or len(self.statement) > 2000:
            raise ValueError("statement is empty or too long")
        if self.language_code not in {"es", "en", "und"}:
            raise ValueError("language_code is invalid")
        if self.claim_type in NON_DETERMINISTIC_TYPES:
            if self.confidence is None or not 0 <= self.confidence <= 1:
                raise ValueError("confidence is required for non-deterministic claims")
            if self.explanation is None or not self.explanation.strip():
                raise ValueError("explanation is required for non-deterministic claims")
        elif self.confidence is not None:
            raise ValueError("confidence is not allowed for deterministic claims")
        if self.origin_type is ClaimOriginType.HUMAN and self.origin_actor_user_id is None:
            raise ValueError("human claims require an actor")
        if self.origin_type is ClaimOriginType.AI and self.claim_type in AI_PROHIBITED_TYPES:
            raise ValueError("AI cannot originate this claim type")
        if self.origin_type in {ClaimOriginType.RULE, ClaimOriginType.SYSTEM} and (
            not self.origin_code or not self.origin_version
        ):
            raise ValueError("rule/system claims require code and version")
        if self.origin_type is ClaimOriginType.AI and (
            not self.provider
            or not self.model
            or not self.prompt_template_version
            or not self.output_schema_version
            or not self.input_fingerprint
        ):
            raise ValueError("AI provenance is incomplete")
        if self.claim_type is ClaimType.HYPOTHESIS and not self.validation_criteria:
            raise ValueError("hypotheses require validation criteria")
        if self.claim_type is ClaimType.HYPOTHESIS and not self.missing_evidence:
            raise ValueError("hypotheses require known missing evidence")
        if self.explanation is not None and len(self.explanation) > 4000:
            raise ValueError("explanation is too long")
        if self.validation_criteria is not None and len(self.validation_criteria) > 2000:
            raise ValueError("validation criteria is too long")
        if len(self.missing_evidence) > 16 or any(
            MISSING_EVIDENCE_CODE.fullmatch(code) is None for code in self.missing_evidence
        ):
            raise ValueError("missing evidence codes are invalid")
        if self.input_fingerprint is not None and len(self.input_fingerprint) != 64:
            raise ValueError("input_fingerprint is invalid")
        if self.idempotency_key is not None and len(self.idempotency_key) != 64:
            raise ValueError("idempotency_key is invalid")


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    evidence_type: EvidenceType
    evidence_id: UUID
    relationship: EvidenceRelationship
    evidence_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.evidence_sha256 is not None and len(self.evidence_sha256) != 64:
            raise ValueError("evidence_sha256 is invalid")


@dataclass(frozen=True, slots=True)
class ClaimAssessment:
    outcome: AssessmentOutcome
    evaluator_user_id: UUID
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation.strip() or len(self.explanation) > 4000:
            raise ValueError("assessment explanation is empty or too long")


def derive_presentation_state(
    *,
    latest_outcome: AssessmentOutcome | None,
    superseded: bool,
    contradicted: bool,
    conflicting_assessments: bool,
) -> ClaimPresentationState:
    if latest_outcome is AssessmentOutcome.RETRACTED:
        return ClaimPresentationState.RETRACTED
    if superseded:
        return ClaimPresentationState.SUPERSEDED
    if contradicted or conflicting_assessments:
        return ClaimPresentationState.CONTESTED
    if latest_outcome is AssessmentOutcome.VALIDATED:
        return ClaimPresentationState.VALIDATED
    if latest_outcome is AssessmentOutcome.REJECTED:
        return ClaimPresentationState.REJECTED
    if latest_outcome is AssessmentOutcome.INSUFFICIENT_EVIDENCE:
        return ClaimPresentationState.INSUFFICIENT_EVIDENCE
    return ClaimPresentationState.PROPOSED
