from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, text

from cyrvanta.modules.incident.infrastructure.models import AlertReferenceModel

# alert_references carries a foreign key to finding_revisions, so that model has
# to be registered before the mapper can be configured.
from cyrvanta.modules.integrations.infrastructure import models as _integration_models  # noqa: F401
from cyrvanta.modules.operations.application.schemas import TopologyNode
from cyrvanta.modules.operations.application.topology_service import NetworkTopologyService
from cyrvanta.shared.database import SessionFactory, tenant_session

_SOURCE = "test-topology-annotation"
_HOST = "lab-topology-fixture"


async def _existing_tenant_id() -> UUID:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        return (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()


async def _seed(tenant_id: UUID, entries: list[tuple[str, str]]) -> None:
    """entries: (title, triage_status)."""
    base = datetime.now(UTC)
    async with tenant_session(tenant_id) as session:
        for position, (title, triage) in enumerate(entries):
            session.add(
                AlertReferenceModel(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    source=_SOURCE,
                    external_id=f"{_SOURCE}-{position}",
                    observed_at=base - timedelta(seconds=position),
                    title=title,
                    category="test",
                    severity="low",
                    provenance="LIVE",
                    is_simulated=False,
                    asset_summary=_HOST,
                    triage_status=triage,
                )
            )


async def _cleanup(tenant_id: UUID) -> None:
    async with tenant_session(tenant_id) as session:
        await session.execute(
            delete(AlertReferenceModel).where(
                AlertReferenceModel.tenant_id == tenant_id,
                AlertReferenceModel.source == _SOURCE,
            )
        )


def _node() -> TopologyNode:
    return TopologyNode(
        id=_HOST,
        name=_HOST,
        type="SERVER",
        category="MONITORED_ASSET",
        ip_address="10.99.0.1",
        ip_addresses=["10.99.0.1"],
        subnet="10.99.0.0/24",
        status="ONLINE",
        latency_ms=None,
        last_ping=datetime.now(UTC).isoformat(),
        services=[],
        active_alerts_count=0,
        active_alerts=[],
        role_description_es="Fixture",
        role_description_en="Fixture",
    )


async def _annotate(tenant_id: UUID) -> TopologyNode:
    node = _node()
    await NetworkTopologyService()._annotate_alerts(
        tenant_id, {_HOST: node}, datetime.now(UTC).isoformat()
    )
    return node


@pytest.mark.asyncio
async def test_discarded_alerts_leave_the_map() -> None:
    """Triage has to change what the map shows, or the badge only ever grows."""
    tenant_id = await _existing_tenant_id()
    await _cleanup(tenant_id)
    await _seed(
        tenant_id,
        [
            ("Alerta pendiente", "UNREVIEWED"),
            ("Alerta confirmada", "RELEVANT"),
            ("Alerta descartada", "DISCARDED"),
            ("Otra descartada", "DISCARDED"),
        ],
    )
    try:
        node = await _annotate(tenant_id)

        titles = {item.title for item in node.active_alerts}
        assert "Alerta descartada" not in titles
        assert "Otra descartada" not in titles
        # Confirming an alert is real does not resolve it, so it stays.
        assert titles == {"Alerta pendiente", "Alerta confirmada"}
        assert node.active_alerts_count == 2
    finally:
        await _cleanup(tenant_id)


@pytest.mark.asyncio
async def test_repeated_titles_collapse_into_one_counted_line() -> None:
    """A host repeating one event used to fill every slot with identical rows.

    The other events it reported were then invisible, which is the opposite of
    what the panel is for.
    """
    tenant_id = await _existing_tenant_id()
    await _cleanup(tenant_id)
    noisy = [("Non service account logged off", "UNREVIEWED") for _ in range(12)]
    await _seed(tenant_id, [*noisy, ("Evento distinto y relevante", "UNREVIEWED")])
    try:
        node = await _annotate(tenant_id)

        titles = [item.title for item in node.active_alerts]
        assert len(titles) == len(set(titles)), "una misma alerta aparece repetida"
        # The distinct event must survive the noise.
        assert "Evento distinto y relevante" in titles

        repeated = next(
            item for item in node.active_alerts if item.title == "Non service account logged off"
        )
        assert repeated.occurrences == 12
        # The badge counts alerts, not lines.
        assert node.active_alerts_count == 13
    finally:
        await _cleanup(tenant_id)
