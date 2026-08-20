"""Filling a slot has to produce something the resolution gate recognises.

The write path and the gate are in different modules and agree only by the
shape of a string. If they ever disagree the failure is silent and cruel: the
analyst fills the file, the screen shows it saved, and resolve keeps refusing
with no way to tell why.
"""

import pytest
from pydantic import ValidationError

from cyrvanta.modules.claims.application.schemas import ClaimCreate
from cyrvanta.modules.incident.domain.resolution import (
    SLOT_PREFIX,
    MissingRequirement,
    ResolutionEvidence,
    TechnicalSlot,
    assess,
)


def payload(**overrides: object) -> dict[str, object]:
    return {
        "claim_type": "INFERENCE",
        "statement": "The account was locked after a credential stuffing burst.",
        "language_code": "en",
        "evidence": [
            {
                "evidence_type": "ALERT_REFERENCE",
                "evidence_id": "0f9b2f6a-3c0f-4c2e-9c4f-2a6a5b1d7e33",
                "relationship": "SUPPORTS",
            }
        ],
        **overrides,
    }


def test_what_a_filled_slot_writes_is_what_the_gate_reads() -> None:
    """The gate strips the prefix and compares to the slot value, so a change
    to either side that breaks the round trip fails here rather than in the
    hands of an analyst who cannot resolve a finished case.
    """
    for slot in TechnicalSlot:
        stored = slot.origin_code
        assert stored.startswith(SLOT_PREFIX)
        assert stored.removeprefix(SLOT_PREFIX) == slot.value


def test_the_three_required_slots_together_satisfy_the_gate() -> None:
    filled = frozenset(
        code.removeprefix(SLOT_PREFIX)
        for code in (
            TechnicalSlot.DIAGNOSIS.origin_code,
            TechnicalSlot.ROOT_CAUSE.origin_code,
            TechnicalSlot.RESOLUTION.origin_code,
        )
    )
    assert assess(ResolutionEvidence(filled, human_notes=1, linked_alerts=1)).ready


def test_an_unknown_slot_is_refused_at_the_edge() -> None:
    """Otherwise it is stored, counts for nothing, and looks filled."""
    with pytest.raises(ValidationError):
        ClaimCreate.model_validate(payload(technical_slot="root_couse"))


def test_a_slot_is_optional_so_ordinary_claims_are_unaffected() -> None:
    assert ClaimCreate.model_validate(payload()).technical_slot is None


def test_a_missing_slot_is_reported_by_name() -> None:
    """The interface can then say which part is missing, in the reader's
    language, instead of a general refusal to resolve.
    """
    missing = assess(ResolutionEvidence(frozenset(), 0, 0)).missing
    assert MissingRequirement.ROOT_CAUSE.value == "root_cause"
    assert MissingRequirement.ROOT_CAUSE in missing
