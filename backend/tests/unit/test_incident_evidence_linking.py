"""An analyst must be able to attach evidence to an incident they opened.

Until this existed, only correlation and the entity-risk sweep could link an
alert to an incident. An incident opened by hand -- the kind that arrives by a
phone call, a CERT notice or an audit finding -- could carry notes and change
status but could never hold a single piece of evidence, which is precisely the
case where the evidence has to be assembled by a person.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text

from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, UserModel
from cyrvanta.modules.incident.application.schemas import IncidentAlertsLink, IncidentCreate
from cyrvanta.modules.incident.application.service import (
    AlertNotFound,
    IncidentConflict,
    IncidentService,
)
from cyrvanta.modules.incident.infrastructure.models import (
    AlertReferenceModel,
    IncidentAlertModel,
    IncidentModel,
    IncidentTimelineModel,
)

# Imported so SQLAlchemy can resolve alert_references.current_revision_id;
# without it the mapper cannot find the table the foreign key targets.
from cyrvanta.modules.integrations.infrastructure.models import FindingRevisionModel  # noqa: F401
from cyrvanta.shared.database import SessionFactory, tenant_session


async def _tenant() -> UUID:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        return (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()


async def _alert(session, tenant_id: UUID, *, simulated: bool = False) -> UUID:
    alert = AlertReferenceModel(
        tenant_id=tenant_id,
        source="test",
        external_id=f"evidence-{uuid4().hex[:10]}",
        observed_at=datetime.now(UTC),
        title="Evidence fixture",
        category="test",
        severity="medium",
        provenance="test-fixture",
        is_simulated=simulated,
    )
    session.add(alert)
    await session.flush()
    return alert.id


@pytest_asyncio.fixture
async def scope():
    tenant_id = await _tenant()
    created: dict[str, list[UUID]] = {"incidents": [], "alerts": []}
    yield tenant_id, created
    async with tenant_session(tenant_id) as session:
        if created["incidents"]:
            await session.execute(
                delete(IncidentAlertModel).where(
                    IncidentAlertModel.incident_id.in_(created["incidents"])
                )
            )
            await session.execute(
                delete(IncidentTimelineModel).where(
                    IncidentTimelineModel.incident_id.in_(created["incidents"])
                )
            )
            await session.execute(
                delete(AuditEventModel).where(AuditEventModel.resource_id.in_(created["incidents"]))
            )
            await session.execute(
                delete(IncidentModel).where(IncidentModel.id.in_(created["incidents"]))
            )
        if created["alerts"]:
            await session.execute(
                delete(AlertReferenceModel).where(AlertReferenceModel.id.in_(created["alerts"]))
            )


async def _actor(tenant_id: UUID) -> UUID:
    async with tenant_session(tenant_id) as session:
        actor = await session.scalar(
            select(UserModel.id).where(UserModel.tenant_id == tenant_id).limit(1)
        )
    assert actor is not None
    return actor


async def _incident(tenant_id: UUID, actor: UUID, created: dict) -> IncidentModel:
    incident = await IncidentService().create_incident(
        tenant_id,
        actor,
        IncidentCreate(
            title="Reported by the help desk",
            description="A user called about a suspicious message",
            severity="medium",
            priority=3,
            classification="reported",
        ),
        uuid4(),
    )
    created["incidents"].append(incident.id)
    return incident


@pytest.mark.asyncio
async def test_an_analyst_can_attach_evidence_to_an_incident_they_opened(scope) -> None:
    tenant_id, created = scope
    actor = await _actor(tenant_id)
    incident = await _incident(tenant_id, actor, created)
    async with tenant_session(tenant_id) as session:
        first, second = await _alert(session, tenant_id), await _alert(session, tenant_id)
    created["alerts"] += [first, second]

    attached = await IncidentService().link_alerts(
        tenant_id,
        incident.id,
        actor,
        IncidentAlertsLink(expected_version=incident.version, alert_ids=[first, second]),
        uuid4(),
    )
    assert {UUID(str(item.id)) for item in attached} == {first, second}


@pytest.mark.asyncio
async def test_attaching_the_same_alert_twice_does_not_duplicate_it(scope) -> None:
    tenant_id, created = scope
    actor = await _actor(tenant_id)
    incident = await _incident(tenant_id, actor, created)
    async with tenant_session(tenant_id) as session:
        alert = await _alert(session, tenant_id)
    created["alerts"].append(alert)

    service = IncidentService()
    await service.link_alerts(
        tenant_id,
        incident.id,
        actor,
        IncidentAlertsLink(expected_version=incident.version, alert_ids=[alert]),
        uuid4(),
    )
    again = await service.link_alerts(
        tenant_id,
        incident.id,
        actor,
        IncidentAlertsLink(expected_version=incident.version + 1, alert_ids=[alert]),
        uuid4(),
    )
    assert len(again) == 1


@pytest.mark.asyncio
async def test_an_unknown_alert_attaches_nothing_at_all(scope) -> None:
    """All or nothing. Attaching five and silently getting three would leave
    the analyst believing evidence is there when it is not.
    """
    tenant_id, created = scope
    actor = await _actor(tenant_id)
    incident = await _incident(tenant_id, actor, created)
    async with tenant_session(tenant_id) as session:
        real = await _alert(session, tenant_id)
    created["alerts"].append(real)

    service = IncidentService()
    with pytest.raises(AlertNotFound):
        await service.link_alerts(
            tenant_id,
            incident.id,
            actor,
            IncidentAlertsLink(expected_version=incident.version, alert_ids=[real, uuid4()]),
            uuid4(),
        )
    assert await service.list_incident_alerts(tenant_id, incident.id) == []


@pytest.mark.asyncio
async def test_a_simulated_alert_can_never_become_evidence(scope) -> None:
    """A demo record must not end up behind a real incident."""
    tenant_id, created = scope
    actor = await _actor(tenant_id)
    incident = await _incident(tenant_id, actor, created)
    async with tenant_session(tenant_id) as session:
        fake = await _alert(session, tenant_id, simulated=True)
    created["alerts"].append(fake)

    with pytest.raises(AlertNotFound):
        await IncidentService().link_alerts(
            tenant_id,
            incident.id,
            actor,
            IncidentAlertsLink(expected_version=incident.version, alert_ids=[fake]),
            uuid4(),
        )


@pytest.mark.asyncio
async def test_a_stale_version_is_refused(scope) -> None:
    """Two analysts on one incident must not overwrite each other in silence."""
    tenant_id, created = scope
    actor = await _actor(tenant_id)
    incident = await _incident(tenant_id, actor, created)
    async with tenant_session(tenant_id) as session:
        alert = await _alert(session, tenant_id)
    created["alerts"].append(alert)

    with pytest.raises(IncidentConflict):
        await IncidentService().link_alerts(
            tenant_id,
            incident.id,
            actor,
            IncidentAlertsLink(expected_version=incident.version + 7, alert_ids=[alert]),
            uuid4(),
        )


@pytest.mark.asyncio
async def test_attaching_evidence_is_recorded_in_the_timeline_and_audited(scope) -> None:
    tenant_id, created = scope
    actor = await _actor(tenant_id)
    incident = await _incident(tenant_id, actor, created)
    async with tenant_session(tenant_id) as session:
        alert = await _alert(session, tenant_id)
    created["alerts"].append(alert)

    await IncidentService().link_alerts(
        tenant_id,
        incident.id,
        actor,
        IncidentAlertsLink(expected_version=incident.version, alert_ids=[alert]),
        uuid4(),
    )

    async with tenant_session(tenant_id) as session:
        entries = list(
            (
                await session.scalars(
                    select(IncidentTimelineModel.entry_type).where(
                        IncidentTimelineModel.incident_id == incident.id
                    )
                )
            ).all()
        )
        actions = list(
            (
                await session.scalars(
                    select(AuditEventModel.action).where(AuditEventModel.resource_id == incident.id)
                )
            ).all()
        )
    assert "evidence_linked" in entries
    assert "incident.evidence.linked" in actions
