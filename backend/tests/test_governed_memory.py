from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cyrvanta.modules.governed_memory.application.schemas import (
    FeedbackCreate,
    MemoryCandidateCreate,
)
from cyrvanta.modules.governed_memory.domain.models import (
    FeedbackOutcome,
    MemoryKind,
    MemorySourceType,
    MemoryStatus,
    ReviewDecision,
    assert_transition,
    review_target,
)


def test_feedback_taxonomy_is_exact() -> None:
    assert {item.value for item in FeedbackOutcome} == {
        "TRUE_POSITIVE",
        "FALSE_POSITIVE",
        "BENIGN_TRUE_POSITIVE",
        "INCONCLUSIVE",
        "ACTION_EFFECTIVE",
        "ACTION_INEFFECTIVE",
        "ACTION_PARTIAL",
        "NOT_ASSESSED",
    }


def test_memory_lifecycle_allows_only_governed_transitions() -> None:
    assert_transition(MemoryStatus.DRAFT, MemoryStatus.IN_REVIEW)
    assert_transition(MemoryStatus.IN_REVIEW, MemoryStatus.APPROVED)
    assert_transition(MemoryStatus.APPROVED, MemoryStatus.ACTIVE)
    assert_transition(MemoryStatus.ACTIVE, MemoryStatus.EXPIRED)
    with pytest.raises(ValueError):
        assert_transition(MemoryStatus.EXPIRED, MemoryStatus.ACTIVE)
    with pytest.raises(ValueError):
        assert_transition(MemoryStatus.DRAFT, MemoryStatus.ACTIVE)


@pytest.mark.parametrize(
    ("decision", "target"),
    [
        (ReviewDecision.APPROVE, MemoryStatus.APPROVED),
        (ReviewDecision.REJECT, MemoryStatus.REJECTED),
        (ReviewDecision.REQUEST_CHANGES, MemoryStatus.DRAFT),
    ],
)
def test_review_decision_has_deterministic_target(
    decision: ReviewDecision, target: MemoryStatus
) -> None:
    assert review_target(decision) is target


def test_feedback_body_forbids_tenant_and_unbounded_reason() -> None:
    material = {
        "resource_type": "INCIDENT",
        "resource_id": uuid4(),
        "outcome": "TRUE_POSITIVE",
        "reason": "confirmed by analyst",
        "occurred_at": datetime.now(UTC),
    }
    assert FeedbackCreate.model_validate(material).outcome is FeedbackOutcome.TRUE_POSITIVE
    with pytest.raises(ValidationError):
        FeedbackCreate.model_validate({**material, "tenant_id": uuid4()})
    with pytest.raises(ValidationError):
        FeedbackCreate.model_validate({**material, "reason": "x" * 1001})


def test_candidate_body_forbids_tenant_and_invalid_window() -> None:
    now = datetime.now(UTC)
    material = {
        "kind": MemoryKind.CASE_NOTE,
        "source_type": MemorySourceType.HUMAN,
        "title_es": "Patrón confirmado",
        "title_en": "Confirmed pattern",
        "statement_es": "Contexto revisado.",
        "statement_en": "Reviewed context.",
        "conditions": {"resource_type": "INCIDENT"},
        "evidence_refs": [uuid4()],
        "valid_from": now,
        "valid_until": now + timedelta(days=30),
    }
    assert MemoryCandidateCreate.model_validate(material).kind is MemoryKind.CASE_NOTE
    with pytest.raises(ValidationError):
        MemoryCandidateCreate.model_validate({**material, "tenant_id": uuid4()})
    with pytest.raises(ValidationError):
        MemoryCandidateCreate.model_validate(
            {**material, "valid_until": now - timedelta(seconds=1)}
        )


def test_migration_declares_rls_append_only_and_separation() -> None:
    from pathlib import Path

    migration = (
        Path(__file__).parents[1] / "alembic" / "versions" / "0019_governed_feedback_memory.py"
    ).read_text(encoding="utf-8")
    for table in (
        "feedback_entries",
        "memory_candidates",
        "memory_candidate_versions",
        "memory_reviews",
        "memory_state_events",
        "memory_influences",
        "memory_metric_definitions",
        "memory_metric_snapshots",
    ):
        assert table in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "REVOKE UPDATE, DELETE" in migration
    assert "enforce_feedback_synthetic_provenance" in migration
    assert "enforce_memory_review_separation" in migration
    assert "enforce_memory_activation_separation" in migration
    assert "SECURITY DEFINER" in migration
    assert "SET search_path = pg_catalog, public" in migration
