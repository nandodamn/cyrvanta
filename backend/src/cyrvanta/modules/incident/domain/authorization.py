"""Whether a person may do something to a *particular* incident.

A permission answers "may this user ever do X?". It is configuration: a tenant
administrator edits roles, and what they grant can change at any time. That is
the wrong place for an invariant the product promises, because a promise that
can be edited away is not a promise.

So the two questions are kept apart. The role decides what someone may attempt.
This decides whether they may do it *here* -- to this incident, given who owns
it and what state it is in -- and it lives in code, where a tenant cannot
loosen it.

The rule that matters: whoever a case is assigned to cannot close it. Not
because they lack the authority in general -- a supervisor assigned an incident
still holds `incident.close` -- but because accepting a resolution is a
judgement about someone else's work, and the person who did the work cannot
make it about their own. It is the same shape the response flow already
enforces, where the requester cannot approve their own proposal.

Framework-free on purpose: it takes what it needs as plain values, so the rules
can be read and tested without a database, a request, or a session.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

# Kept in step with TRANSITIONS in the incident service, which decides which
# moves exist at all. This module decides who may make them.
TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"triaged", "closed"}),
    "triaged": frozenset({"investigating", "closed"}),
    "investigating": frozenset({"contained", "resolved", "closed"}),
    "contained": frozenset({"investigating", "resolved"}),
    "resolved": frozenset({"closed", "reopened"}),
    "closed": frozenset({"reopened"}),
    "reopened": frozenset({"investigating", "contained", "resolved", "closed"}),
}


class IncidentAction(StrEnum):
    READ = "read"
    UPDATE = "update"
    ASSIGN = "assign"
    LINK_EVIDENCE = "link_evidence"
    TRANSITION_TRIAGED = "transition:triaged"
    TRANSITION_INVESTIGATING = "transition:investigating"
    TRANSITION_CONTAINED = "transition:contained"
    TRANSITION_RESOLVED = "transition:resolved"
    TRANSITION_CLOSED = "transition:closed"
    TRANSITION_REOPENED = "transition:reopened"

    @property
    def target_status(self) -> str | None:
        prefix, _, status = self.value.partition(":")
        return status if prefix == "transition" else None


class Denial(StrEnum):
    """Why an action is unavailable.

    Reported as a code rather than a sentence so the interface can say it in
    the reader's language, and so an audit can distinguish "lacked the
    permission" from "was the owner of the case".
    """

    MISSING_PERMISSION = "missing_permission"
    INVALID_TRANSITION = "invalid_transition"
    OWNER_CANNOT_CLOSE = "owner_cannot_close"
    NOT_THE_OWNER = "not_the_owner"


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: UUID
    permissions: frozenset[str]


@dataclass(frozen=True, slots=True)
class IncidentFacts:
    status: str
    assignee_user_id: UUID | None

    def is_owner(self, actor: Actor) -> bool:
        return self.assignee_user_id is not None and self.assignee_user_id == actor.user_id


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    reason: Denial | None = None


ALLOWED = Decision(True)


def _denied(reason: Denial) -> Decision:
    return Decision(False, reason)


def can(actor: Actor, incident: IncidentFacts, action: IncidentAction) -> Decision:
    target = action.target_status
    if target is None:
        required = {
            IncidentAction.READ: "incident.read",
            IncidentAction.UPDATE: "incident.update",
            IncidentAction.ASSIGN: "incident.assign",
            IncidentAction.LINK_EVIDENCE: "incident.update",
        }[action]
        if required not in actor.permissions:
            return _denied(Denial.MISSING_PERMISSION)
        return ALLOWED

    if target not in TRANSITIONS.get(incident.status, frozenset()):
        return _denied(Denial.INVALID_TRANSITION)

    if target == "resolved":
        if "incident.resolve" not in actor.permissions:
            return _denied(Denial.MISSING_PERMISSION)
        # An incident with an owner is theirs to declare resolved. A supervisor
        # may still do it -- they hold incident.close -- but a second analyst
        # cannot finish someone else's case from the side.
        if (
            incident.assignee_user_id is not None
            and not incident.is_owner(actor)
            and "incident.close" not in actor.permissions
        ):
            return _denied(Denial.NOT_THE_OWNER)
        return ALLOWED

    if target in {"closed", "reopened"}:
        if "incident.close" not in actor.permissions:
            return _denied(Denial.MISSING_PERMISSION)
        # The invariant. Reopening is exempt: it is the opposite of approving
        # your own work -- it is admitting the case is not finished.
        if target == "closed" and incident.is_owner(actor):
            return _denied(Denial.OWNER_CANNOT_CLOSE)
        return ALLOWED

    if "incident.update" not in actor.permissions:
        return _denied(Denial.MISSING_PERMISSION)
    return ALLOWED


def allowed_actions(actor: Actor, incident: IncidentFacts) -> tuple[IncidentAction, ...]:
    """Exactly what this person can do to this incident, right now.

    The interface builds its menu from this instead of showing everything and
    disabling most of it: an action a user can never take is noise, and an
    action that is offered and then refused teaches people not to trust the
    screen.
    """
    return tuple(action for action in IncidentAction if can(actor, incident, action).allowed)
