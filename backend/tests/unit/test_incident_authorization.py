"""Who may act on a particular incident.

The permission decides what someone may ever attempt; these rules decide
whether they may do it here. They live in code rather than in role
configuration because a tenant administrator can edit a role, and an invariant
that can be edited away is not one.
"""

from uuid import uuid4

import pytest

from cyrvanta.modules.incident.domain.authorization import (
    Actor,
    Denial,
    IncidentAction,
    IncidentFacts,
    allowed_actions,
    can,
)

ANALYST = frozenset(
    {"incident.read", "incident.update", "incident.resolve", "alert.read", "claim.create"}
)
SUPERVISOR = ANALYST | {"incident.close", "incident.assign"}
READER = frozenset({"incident.read"})

OWNER = uuid4()
SOMEONE_ELSE = uuid4()


def actor(permissions: frozenset[str], user_id=SOMEONE_ELSE) -> Actor:
    return Actor(user_id=user_id, permissions=permissions)


def incident(status: str, assignee=None) -> IncidentFacts:
    return IncidentFacts(status=status, assignee_user_id=assignee)


def test_the_owner_of_a_case_cannot_close_it() -> None:
    """The invariant the whole design rests on. Not for want of authority --
    this actor holds incident.close -- but because accepting a resolution is a
    judgement about someone else's work.
    """
    decision = can(
        actor(SUPERVISOR, user_id=OWNER),
        incident("resolved", assignee=OWNER),
        IncidentAction.TRANSITION_CLOSED,
    )
    assert decision.allowed is False
    assert decision.reason is Denial.OWNER_CANNOT_CLOSE


def test_a_supervisor_closes_a_case_that_is_not_theirs() -> None:
    assert can(
        actor(SUPERVISOR, user_id=SOMEONE_ELSE),
        incident("resolved", assignee=OWNER),
        IncidentAction.TRANSITION_CLOSED,
    ).allowed


def test_granting_close_to_an_analyst_does_not_let_them_close_their_own() -> None:
    """The reason this is not left to role configuration. A tenant can add
    incident.close to the analyst role at any time; the invariant has to
    survive that.
    """
    generous = ANALYST | {"incident.close"}
    assert (
        can(
            actor(generous, user_id=OWNER),
            incident("resolved", assignee=OWNER),
            IncidentAction.TRANSITION_CLOSED,
        ).reason
        is Denial.OWNER_CANNOT_CLOSE
    )


def test_an_unassigned_incident_can_be_closed_by_anyone_holding_the_permission() -> None:
    """With nobody accountable for it there is no self-approval to prevent,
    and refusing would leave the case permanently open.
    """
    assert can(actor(SUPERVISOR), incident("resolved"), IncidentAction.TRANSITION_CLOSED).allowed


def test_the_owner_may_still_reopen_their_own_case() -> None:
    """Reopening is the opposite of approving your own work: it is admitting
    the case is not finished.
    """
    assert can(
        actor(SUPERVISOR, user_id=OWNER),
        incident("resolved", assignee=OWNER),
        IncidentAction.TRANSITION_REOPENED,
    ).allowed


def test_the_owner_declares_their_own_case_resolved() -> None:
    assert can(
        actor(ANALYST, user_id=OWNER),
        incident("investigating", assignee=OWNER),
        IncidentAction.TRANSITION_RESOLVED,
    ).allowed


def test_another_analyst_cannot_finish_someone_else_s_case() -> None:
    decision = can(
        actor(ANALYST, user_id=SOMEONE_ELSE),
        incident("investigating", assignee=OWNER),
        IncidentAction.TRANSITION_RESOLVED,
    )
    assert decision.allowed is False
    assert decision.reason is Denial.NOT_THE_OWNER


def test_a_supervisor_may_resolve_a_case_owned_by_someone_else() -> None:
    assert can(
        actor(SUPERVISOR, user_id=SOMEONE_ELSE),
        incident("investigating", assignee=OWNER),
        IncidentAction.TRANSITION_RESOLVED,
    ).allowed


def test_an_analyst_without_the_close_permission_cannot_close_anything() -> None:
    assert (
        can(actor(ANALYST), incident("resolved"), IncidentAction.TRANSITION_CLOSED).reason
        is Denial.MISSING_PERMISSION
    )


def test_a_move_the_state_machine_does_not_allow_is_refused_before_permissions() -> None:
    """Reported as an invalid transition rather than a missing permission: the
    move does not exist from here, and saying "you lack a permission" would
    send someone looking for a role that would not have helped.
    """
    assert (
        can(actor(SUPERVISOR), incident("new"), IncidentAction.TRANSITION_RESOLVED).reason
        is Denial.INVALID_TRANSITION
    )


def test_a_reader_can_only_read() -> None:
    assert allowed_actions(actor(READER), incident("investigating")) == (IncidentAction.READ,)


def test_the_menu_is_what_this_person_can_do_to_this_incident() -> None:
    """An owner looking at their resolved case: everything except closing it."""
    available = allowed_actions(
        actor(SUPERVISOR, user_id=OWNER), incident("resolved", assignee=OWNER)
    )
    assert IncidentAction.TRANSITION_REOPENED in available
    assert IncidentAction.TRANSITION_CLOSED not in available
    assert IncidentAction.ASSIGN in available


@pytest.mark.parametrize(
    "action",
    [IncidentAction.READ, IncidentAction.UPDATE, IncidentAction.ASSIGN],
)
def test_actions_that_are_not_transitions_need_only_their_permission(action) -> None:
    assert can(actor(SUPERVISOR), incident("new"), action).allowed
