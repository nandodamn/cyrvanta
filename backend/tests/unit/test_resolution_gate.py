"""What an incident must carry before it can be called resolved.

Marking a case technically resolved is a claim about work that someone else
will be asked to accept. Made against an empty file it is unreviewable: the
supervisor is approving a conclusion with nothing behind it, and months later
nobody can reconstruct what was done or why.
"""

import pytest

from cyrvanta.modules.incident.domain.resolution import (
    MissingRequirement,
    ResolutionEvidence,
    TechnicalSlot,
    assess,
)


def evidence(*slots: TechnicalSlot, notes: int = 1, alerts: int = 1) -> ResolutionEvidence:
    return ResolutionEvidence(
        filled_slots=frozenset(slot.value for slot in slots),
        human_notes=notes,
        linked_alerts=alerts,
    )


COMPLETE = (TechnicalSlot.DIAGNOSIS, TechnicalSlot.ROOT_CAUSE, TechnicalSlot.RESOLUTION)


def test_a_complete_file_is_ready() -> None:
    assert assess(evidence(*COMPLETE)).ready


def test_an_empty_incident_lists_everything_it_lacks() -> None:
    """All of it at once, so an analyst is told what to go and do rather than
    discovering the next missing piece one refusal at a time.
    """
    missing = assess(ResolutionEvidence(frozenset(), 0, 0)).missing
    assert set(missing) == set(MissingRequirement)


def test_an_undetermined_root_cause_is_accepted_when_it_is_recorded_as_such() -> None:
    """Some incidents genuinely end without a cause. Demanding one anyway
    produces invented causes, which is worse than an honest "could not be
    determined" that a reviewer can weigh.
    """
    assert assess(
        evidence(
            TechnicalSlot.DIAGNOSIS,
            TechnicalSlot.ROOT_CAUSE_UNDETERMINED,
            TechnicalSlot.RESOLUTION,
        )
    ).ready


def test_leaving_the_cause_blank_is_not_the_same_as_saying_it_is_unknown() -> None:
    readiness = assess(evidence(TechnicalSlot.DIAGNOSIS, TechnicalSlot.RESOLUTION))
    assert MissingRequirement.ROOT_CAUSE in readiness.missing


@pytest.mark.parametrize(
    ("missing_slot", "expected"),
    [
        (TechnicalSlot.DIAGNOSIS, MissingRequirement.DIAGNOSIS),
        (TechnicalSlot.RESOLUTION, MissingRequirement.RESOLUTION),
    ],
)
def test_each_required_part_is_named_when_it_is_absent(missing_slot, expected) -> None:
    present = tuple(slot for slot in COMPLETE if slot is not missing_slot)
    assert expected in assess(evidence(*present)).missing


def test_a_resolution_needs_a_note_written_by_a_person() -> None:
    """Status changes write to the timeline on their own, so the count is of
    human notes: counting every entry would let the gate satisfy itself.
    """
    assert MissingRequirement.TECHNICAL_NOTE in assess(evidence(*COMPLETE, notes=0)).missing


def test_a_resolution_needs_something_it_was_based_on() -> None:
    assert MissingRequirement.EVIDENCE in assess(evidence(*COMPLETE, alerts=0)).missing


def test_the_optional_parts_of_the_file_are_never_demanded() -> None:
    """The file can hold affected systems, indicators, residual risk and more.
    None of it is required: a checklist long enough to be resented is one
    people learn to fill with nothing.
    """
    optional = (
        TechnicalSlot.AFFECTED_SYSTEMS,
        TechnicalSlot.INDICATORS,
        TechnicalSlot.RESIDUAL_RISK,
        TechnicalSlot.PREVENTIVE_MEASURES,
    )
    assert assess(evidence(*COMPLETE)).ready
    assert assess(evidence(*COMPLETE, *optional)).ready


def test_a_slot_maps_to_the_origin_code_the_claim_ledger_stores() -> None:
    """The file lives in the claim ledger rather than in flat columns, so each
    entry keeps its provenance: who asserted it, on what evidence, and whether
    anyone assessed it.
    """
    assert TechnicalSlot.ROOT_CAUSE.origin_code == "technical-file:root_cause"
