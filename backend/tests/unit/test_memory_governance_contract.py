"""The promises this module makes about who may do what to a memory.

The module's whole argument is that an operational lesson reaches the screen
only after someone other than its author agreed it should. That is enforced in
code rather than in permissions, because a permission is configuration a
tenant administrator can edit, and a promise that can be edited away is not a
promise.

These read the service source rather than exercising a database. The rules
they guard are single conditions in known places; a test that needs a live
Postgres to prove "the author cannot review" is a test nobody runs.
"""

import re
from pathlib import Path

import pytest

from cyrvanta.modules.governed_memory.domain.models import (
    TERMINAL_MEMORY_STATUSES,
    MemoryStatus,
    ReviewDecision,
    assert_transition,
    review_target,
)

SERVICE = Path("src/cyrvanta/modules/governed_memory/application/service.py").read_text(
    encoding="utf-8"
)
ROUTER = Path("src/cyrvanta/modules/governed_memory/presentation/router.py").read_text(
    encoding="utf-8"
)
COLLAPSED = re.sub(r"\s+", " ", SERVICE)


def test_the_author_of_a_version_cannot_review_or_activate_it() -> None:
    """Read off the version, not the candidate.

    A correction is a new version written by whoever corrects it. Checking the
    candidate's author would have protected the wrong person the moment two
    people worked on one memory: the original author blocked from reviewing
    work they did not write, and the actual writer free to approve their own.
    """
    assert "version.created_by_user_id == actor_user_id" in COLLAPSED
    assert "actor_user_id == version.created_by_user_id" in COLLAPSED
    assert "candidate.created_by_user_id == actor_user_id" not in COLLAPSED


def test_a_memory_cannot_be_corrected_while_someone_is_reviewing_it() -> None:
    """Otherwise a reviewer approves text that no longer exists."""
    assert "Finish the current review before correcting" in SERVICE


def test_correcting_a_live_memory_supersedes_it_at_once() -> None:
    """Leaving the old one active while its replacement waits for review would
    keep showing advice somebody has already judged wrong.
    """
    assert "MemoryStatus.SUPERSEDED" in SERVICE
    assert "superseded_by_v" in SERVICE


def test_a_correction_never_edits_the_version_it_replaces() -> None:
    """The point of storing versions: an approved statement that can be
    rewritten in place is an approval of nothing.
    """
    assert "update(MemoryCandidateVersionModel)" not in COLLAPSED
    assert "update(MemoryReviewModel)" not in COLLAPSED
    assert "update(MemoryStateEventModel)" not in COLLAPSED
    assert "previous.version + 1" in COLLAPSED


def test_terminal_states_never_return_to_active() -> None:
    for status in TERMINAL_MEMORY_STATUSES:
        with pytest.raises(ValueError):
            assert_transition(status, MemoryStatus.ACTIVE)


def test_asking_for_changes_returns_the_memory_to_its_author() -> None:
    """And now has somewhere to go: the correction endpoint. Before it
    existed this was a dead end -- back to draft, where the only possible act
    was to submit the identical text again.
    """
    assert review_target(ReviewDecision.REQUEST_CHANGES) is MemoryStatus.DRAFT
    assert "/memory-candidates/{candidate_id}/versions" in ROUTER


def test_the_incident_context_is_built_from_the_incident() -> None:
    """A caller that chooses its own facts chooses its own matches, and the
    fingerprint is supposed to be evidence of what the case actually was.
    """
    assert "async def incident_context" in SERVICE
    assert '"severity": incident.severity' in SERVICE
    assert 'consumer_type="INCIDENT_VIEW"' in SERVICE


def test_consulting_the_same_memory_twice_is_recorded_once() -> None:
    """Opening an incident is not an event. Recording one influence row per
    page view would grow the ledger until it stopped being readable as a
    record of where memory was actually used.
    """
    assert "MemoryInfluenceModel.idempotency_key == key" in COLLAPSED
    assert "incident-view:" in SERVICE


def test_influence_stays_observational() -> None:
    """The ADR permits memory to be shown and nothing else. Anything that
    reached into another module from here would be the first step towards a
    memory that decides.
    """
    assert "OBSERVATIONAL_ONLY" in SERVICE
    for forbidden in ("IncidentService", "DecisionService", "PlaybookService"):
        assert forbidden not in SERVICE
