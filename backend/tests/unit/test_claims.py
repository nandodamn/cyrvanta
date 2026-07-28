from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cyrvanta.modules.claims.domain.models import (
    AssessmentOutcome,
    Claim,
    ClaimOriginType,
    ClaimPresentationState,
    ClaimType,
    derive_presentation_state,
)


def claim(**overrides: object) -> Claim:
    values: dict[str, object] = {
        "claim_id": uuid4(),
        "tenant_id": uuid4(),
        "incident_id": uuid4(),
        "claim_type": ClaimType.INFERENCE,
        "statement": "The observed sequence may indicate credential abuse.",
        "language_code": "en",
        "confidence": 0.65,
        "origin_type": ClaimOriginType.RULE,
        "origin_actor_user_id": None,
        "origin_code": "incident-analysis",
        "origin_version": "1",
        "provider": None,
        "model": None,
        "prompt_template_version": None,
        "output_schema_version": None,
        "input_fingerprint": None,
        "explanation": "Evidence-bounded deterministic analysis.",
        "validation_criteria": None,
        "missing_evidence": (),
        "is_simulated": False,
        "correlation_id": uuid4(),
        "causation_id": None,
        "created_at": datetime.now(UTC),
    }
    values.update(overrides)
    return Claim(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "reserved", [ClaimType.DECISION, ClaimType.ACTION, ClaimType.RESULT]
)
def test_reserved_claim_types_fail_closed(reserved: ClaimType) -> None:
    with pytest.raises(ValueError, match="reserved"):
        claim(claim_type=reserved, confidence=None)


def test_ai_cannot_originate_a_fact() -> None:
    with pytest.raises(ValueError, match="AI cannot"):
        claim(
            claim_type=ClaimType.FACT,
            confidence=None,
            origin_type=ClaimOriginType.AI,
            origin_code=None,
            origin_version=None,
            provider="ollama",
            model="gemma4",
            prompt_template_version="incident-summary-v1",
            output_schema_version="summary-v1",
            input_fingerprint="a" * 64,
        )


def test_inference_requires_bounded_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        claim(confidence=None)


def test_inference_requires_explanation() -> None:
    with pytest.raises(ValueError, match="explanation"):
        claim(explanation=None)


def test_hypothesis_requires_known_missing_evidence() -> None:
    with pytest.raises(ValueError, match="missing evidence"):
        claim(
            claim_type=ClaimType.HYPOTHESIS,
            validation_criteria="Confirm the source identity.",
            missing_evidence=(),
        )


def test_assessment_changes_state_without_changing_claim_type() -> None:
    original = claim()
    state = derive_presentation_state(
        latest_outcome=AssessmentOutcome.VALIDATED,
        superseded=False,
        contradicted=False,
        conflicting_assessments=False,
    )
    assert original.claim_type is ClaimType.INFERENCE
    assert state is ClaimPresentationState.VALIDATED


def test_contradiction_is_presented_as_contested() -> None:
    assert (
        derive_presentation_state(
            latest_outcome=AssessmentOutcome.VALIDATED,
            superseded=False,
            contradicted=True,
            conflicting_assessments=False,
        )
        is ClaimPresentationState.CONTESTED
    )
