"""What an incident must carry before it can be called resolved.

Marking a case technically resolved is a claim about work that someone else
will be asked to accept. Made against an empty file it is unreviewable: the
supervisor is being asked to approve a conclusion with nothing behind it, and
six months later nobody can reconstruct what was done or why.

So the gate asks for the least that makes a resolution reviewable, and no more:
what happened, why it happened, what was done about it, a human account of the
work, and at least one piece of evidence. Everything else the technical file
can hold -- affected systems, indicators, residual risk -- is useful and is not
demanded, because a checklist long enough to be resented is a checklist people
learn to fill with nothing.

Root cause has a deliberate escape hatch. Some incidents genuinely end without
one, and forcing a value there would produce invented causes, which is worse
than an honest "could not be determined" that a reviewer can weigh.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Slots are stored as `origin_code = "technical-file:<slot>"`, following the
# convention incident analysis already uses, so the claim ledger keeps holding
# the provenance -- who asserted it, on what evidence, and whether anyone
# has assessed it -- instead of a flat column that can answer none of that.
SLOT_PREFIX = "technical-file:"


class TechnicalSlot(StrEnum):
    DIAGNOSIS = "diagnosis"
    PROBABLE_CAUSE = "probable_cause"
    ROOT_CAUSE = "root_cause"
    ROOT_CAUSE_UNDETERMINED = "root_cause_undetermined"
    AFFECTED_SYSTEMS = "affected_systems"
    INVOLVED_ASSETS = "involved_assets"
    VULNERABILITIES = "vulnerabilities"
    INDICATORS = "indicators"
    TECHNICAL_IMPACT = "technical_impact"
    OBSERVATIONS = "observations"
    RESOLUTION = "resolution"
    MITIGATION = "mitigation"
    CORRECTIVE_MEASURES = "corrective_measures"
    PREVENTIVE_MEASURES = "preventive_measures"
    RESIDUAL_RISK = "residual_risk"
    RESTORED_SERVICES = "restored_services"

    @property
    def origin_code(self) -> str:
        return f"{SLOT_PREFIX}{self.value}"


class MissingRequirement(StrEnum):
    """Named rather than described, so the interface can say it in the
    reader's language and a test can assert on the requirement itself.
    """

    DIAGNOSIS = "diagnosis"
    ROOT_CAUSE = "root_cause"
    RESOLUTION = "resolution"
    TECHNICAL_NOTE = "technical_note"
    EVIDENCE = "evidence"


@dataclass(frozen=True, slots=True)
class ResolutionEvidence:
    """What the incident actually has, reduced to what the gate weighs."""

    filled_slots: frozenset[str]
    human_notes: int
    linked_alerts: int


@dataclass(frozen=True, slots=True)
class Readiness:
    missing: tuple[MissingRequirement, ...]

    @property
    def ready(self) -> bool:
        return not self.missing


def assess(evidence: ResolutionEvidence) -> Readiness:
    missing: list[MissingRequirement] = []

    if TechnicalSlot.DIAGNOSIS.value not in evidence.filled_slots:
        missing.append(MissingRequirement.DIAGNOSIS)

    # Either the cause, or a recorded reason it could not be established.
    # Demanding a cause outright would produce invented ones.
    if (
        not {
            TechnicalSlot.ROOT_CAUSE.value,
            TechnicalSlot.ROOT_CAUSE_UNDETERMINED.value,
        }
        & evidence.filled_slots
    ):
        missing.append(MissingRequirement.ROOT_CAUSE)

    if TechnicalSlot.RESOLUTION.value not in evidence.filled_slots:
        missing.append(MissingRequirement.RESOLUTION)

    # A note written by a person. Status changes write to the timeline on their
    # own, so counting every entry would let the gate satisfy itself.
    if evidence.human_notes < 1:
        missing.append(MissingRequirement.TECHNICAL_NOTE)

    if evidence.linked_alerts < 1:
        missing.append(MissingRequirement.EVIDENCE)

    return Readiness(tuple(missing))
