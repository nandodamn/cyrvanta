"""When the feedback ledger is saying something worth writing down.

The SOC records outcomes case by case; nobody reads a hundred of them looking
for a shape. This finds the shape -- a run of identically judged cases sharing
a classification -- and hands it to a person as a draft lesson.

Deliberately arithmetic, not inference. The decision to propose is a count over
a window that a supervisor can redo by hand; only the *wording* of the proposal
is left to a model, and even that is validated before it is stored. A system
that decided what to propose by asking a model what looks interesting would be
unable to say why it proposed anything, which is the failure this whole module
exists to avoid.

Nothing here activates. A suggestion is a draft with no human author, and it
travels the same review and activation path as one a person wrote.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

# Below this a "pattern" is a coincidence. Four cases judged the same way about
# the same class of incident is thin evidence, and it is offered as a draft
# rather than a conclusion -- but three would fill the review queue with noise,
# and a queue people stop reading is worse than no suggestions.
MINIMUM_OCCURRENCES = 4


@dataclass(frozen=True, slots=True)
class FeedbackFact:
    """One assessed case, reduced to what a pattern is made of."""

    feedback_id: UUID
    outcome: str
    classification: str


@dataclass(frozen=True, slots=True)
class Pattern:
    outcome: str
    classification: str
    evidence: tuple[UUID, ...]

    @property
    def signature(self) -> str:
        """Identifies the pattern, not the run that found it.

        Used as the idempotency key, so a second sweep over the same feedback
        recognises the suggestion it already made instead of proposing it
        again every fifteen seconds.
        """
        return f"ai-suggestion:{self.outcome}:{self.classification}"


def find_patterns(facts: list[FeedbackFact], minimum: int = MINIMUM_OCCURRENCES) -> list[Pattern]:
    """Runs of the same judgement about the same kind of case.

    Only outcomes that say something happened: a pattern of INCONCLUSIVE tells
    you the SOC could not decide, which is worth knowing and is not a lesson
    about the environment.
    """
    grouped: dict[tuple[str, str], list[UUID]] = {}
    for fact in facts:
        if fact.outcome in {"INCONCLUSIVE", "NOT_ASSESSED"}:
            continue
        if not fact.classification:
            continue
        grouped.setdefault((fact.outcome, fact.classification), []).append(fact.feedback_id)

    patterns = [
        Pattern(outcome=outcome, classification=classification, evidence=tuple(ids))
        for (outcome, classification), ids in grouped.items()
        if len(ids) >= minimum
    ]
    # Strongest first: a reviewer working down the queue should meet the
    # best-evidenced suggestion before the thinnest one.
    return sorted(patterns, key=lambda item: (-len(item.evidence), item.signature))


def fallback_wording(pattern: Pattern) -> tuple[str, str, str, str]:
    """What to propose when no model is available.

    Plain and dull on purpose. The suggestion's value is the pattern and the
    evidence attached to it; a model makes the sentence readable and is not
    allowed to be the reason the sentence exists.
    """
    count = len(pattern.evidence)
    title_es = f"{count} casos de {pattern.classification} evaluados como {pattern.outcome}"
    title_en = f"{count} {pattern.classification} cases assessed as {pattern.outcome}"
    statement_es = (
        f"En los últimos casos de {pattern.classification}, {count} fueron evaluados como "
        f"{pattern.outcome}. Revisar si corresponde ajustar el triaje de esta clasificación."
    )
    statement_en = (
        f"Among recent {pattern.classification} cases, {count} were assessed as "
        f"{pattern.outcome}. Consider whether triage for this classification needs adjusting."
    )
    return title_es, title_en, statement_es, statement_en
