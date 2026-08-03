from enum import StrEnum


class FeedbackOutcome(StrEnum):
    TRUE_POSITIVE = "TRUE_POSITIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    BENIGN_TRUE_POSITIVE = "BENIGN_TRUE_POSITIVE"
    INCONCLUSIVE = "INCONCLUSIVE"
    ACTION_EFFECTIVE = "ACTION_EFFECTIVE"
    ACTION_INEFFECTIVE = "ACTION_INEFFECTIVE"
    ACTION_PARTIAL = "ACTION_PARTIAL"
    NOT_ASSESSED = "NOT_ASSESSED"


class MemoryKind(StrEnum):
    CASE_NOTE = "CASE_NOTE"
    TREND = "TREND"


class MemorySourceType(StrEnum):
    HUMAN = "HUMAN"
    AI_SUGGESTED = "AI_SUGGESTED"


class ReviewDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class MemoryStatus(StrEnum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    DISABLED = "DISABLED"
    SUPERSEDED = "SUPERSEDED"


TERMINAL_MEMORY_STATUSES = {
    MemoryStatus.REJECTED,
    MemoryStatus.EXPIRED,
    MemoryStatus.DISABLED,
    MemoryStatus.SUPERSEDED,
}


def review_target(decision: ReviewDecision) -> MemoryStatus:
    if decision is ReviewDecision.APPROVE:
        return MemoryStatus.APPROVED
    if decision is ReviewDecision.REJECT:
        return MemoryStatus.REJECTED
    return MemoryStatus.DRAFT


def assert_transition(current: MemoryStatus, target: MemoryStatus) -> None:
    allowed = {
        MemoryStatus.DRAFT: {MemoryStatus.IN_REVIEW},
        MemoryStatus.IN_REVIEW: {
            MemoryStatus.APPROVED,
            MemoryStatus.REJECTED,
            MemoryStatus.DRAFT,
        },
        MemoryStatus.APPROVED: {MemoryStatus.ACTIVE, MemoryStatus.DISABLED},
        MemoryStatus.ACTIVE: {
            MemoryStatus.EXPIRED,
            MemoryStatus.DISABLED,
            MemoryStatus.SUPERSEDED,
        },
    }
    if target not in allowed.get(current, set()):
        raise ValueError(f"Invalid memory transition: {current} -> {target}")
