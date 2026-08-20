"""The incident's record has to answer an auditor's question.

Who did what, when, from which value, to which, and why. Every audit event
this module wrote carried an empty `details`, so the trail could say a status
had changed but not from what, to what, or for what reason -- it had to be
inferred from a sentence written for a human, which is prose and cannot be
relied on months later.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text

from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, UserModel
from cyrvanta.modules.incident.application.schemas import (
    IncidentAssign,
    IncidentCreate,
    IncidentTransition,
)
from cyrvanta.modules.incident.application.service import IncidentService
from cyrvanta.modules.incident.infrastructure.models import IncidentModel, IncidentTimelineModel
from cyrvanta.shared.database import SessionFactory, tenant_session


async def _tenant() -> UUID:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        return (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()


@pytest_asyncio.fixture
async def case():
    tenant_id = await _tenant()
    async with tenant_session(tenant_id) as session:
        actor = await session.scalar(
            select(UserModel.id).where(UserModel.tenant_id == tenant_id).limit(1)
        )
    incident = await IncidentService().create_incident(
        tenant_id,
        actor,
        IncidentCreate(
            title="Reported by a partner",
            description="A third party notified us",
            severity="medium",
            priority=3,
            classification="reported",
        ),
        uuid4(),
    )
    yield tenant_id, actor, incident.id
    async with tenant_session(tenant_id) as session:
        await session.execute(
            delete(IncidentTimelineModel).where(IncidentTimelineModel.incident_id == incident.id)
        )
        await session.execute(
            delete(AuditEventModel).where(AuditEventModel.resource_id == incident.id)
        )
        await session.execute(delete(IncidentModel).where(IncidentModel.id == incident.id))


def _entry(history, action: str):
    return next(item for item in history if item.action == action)


@pytest.mark.asyncio
async def test_a_status_change_records_what_it_moved_from_and_to(case) -> None:
    tenant_id, actor, incident_id = case
    service = IncidentService()
    await service.transition(
        tenant_id,
        actor,
        incident_id,
        IncidentTransition(expected_version=1, target_status="triaged", reason="Taking it on"),
        uuid4(),
        frozenset({"incident.update"}),
    )

    entry = _entry(await service.history(tenant_id, incident_id), "incident.status.changed")
    assert entry.before == {"status": "new"}
    assert entry.after == {"status": "triaged"}
    assert entry.reason == "Taking it on"


@pytest.mark.asyncio
async def test_the_record_says_what_the_actor_was_to_this_incident(case) -> None:
    """Stored at the time, not resolved on read. Assignments move, and asking
    today who owns it would answer about now rather than about then.
    """
    tenant_id, actor, incident_id = case
    service = IncidentService()
    await service.assign(
        tenant_id,
        actor,
        incident_id,
        IncidentAssign(expected_version=1, assignee_user_id=actor),
        uuid4(),
    )
    await service.transition(
        tenant_id,
        actor,
        incident_id,
        IncidentTransition(expected_version=2, target_status="triaged", reason="Mine now"),
        uuid4(),
        frozenset({"incident.update"}),
    )

    history = await service.history(tenant_id, incident_id)
    assert _entry(history, "incident.status.changed").actor_relation == "owner"
    assert _entry(history, "incident.status.changed").actor_roles != []


@pytest.mark.asyncio
async def test_an_assignment_records_who_held_it_before(case) -> None:
    """Never overwritten in silence: the previous holder is part of the record,
    and it is read before the assignment moves so a reassignment does not look
    as though the incoming owner made it.
    """
    tenant_id, actor, incident_id = case
    service = IncidentService()
    await service.assign(
        tenant_id,
        actor,
        incident_id,
        IncidentAssign(expected_version=1, assignee_user_id=actor),
        uuid4(),
    )

    entry = _entry(await service.history(tenant_id, incident_id), "incident.assigned")
    assert entry.before == {"assignee_user_id": ""}
    assert entry.after == {"assignee_user_id": str(actor)}
    assert entry.actor_relation == "not_owner"


@pytest.mark.asyncio
async def test_the_history_merges_both_sources_newest_first(case) -> None:
    tenant_id, actor, incident_id = case
    service = IncidentService()
    await service.transition(
        tenant_id,
        actor,
        incident_id,
        IncidentTransition(expected_version=1, target_status="triaged", reason="Taking it on"),
        uuid4(),
        frozenset({"incident.update"}),
    )

    history = await service.history(tenant_id, incident_id)
    assert {item.source for item in history} == {"audit", "timeline"}
    assert history == sorted(history, key=lambda item: item.occurred_at, reverse=True)


@pytest.mark.asyncio
async def test_an_automatic_event_is_not_attributed_to_a_person(case) -> None:
    """Correlation and the risk sweep write here too. Naming someone for their
    work would be a lie in the one record meant to be trusted.
    """
    tenant_id, actor, incident_id = case
    async with tenant_session(tenant_id) as session:
        session.add(
            IncidentTimelineModel(
                tenant_id=tenant_id,
                incident_id=incident_id,
                actor_user_id=None,
                entry_type="correlated",
                summary="rule matched",
                incident_version=1,
                effective_at=datetime.now(UTC),
            )
        )

    entry = _entry(await IncidentService().history(tenant_id, incident_id), "correlated")
    assert entry.actor_email is None
    assert entry.actor_name is None
