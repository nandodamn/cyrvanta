from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, text

from cyrvanta.modules.incident.application.service import (
    SEVERITY_ORDER,
    IncidentService,
)
from cyrvanta.modules.incident.infrastructure.models import AlertReferenceModel

# alert_references carries a foreign key to finding_revisions, so that model has
# to be registered before the mapper can be configured.
from cyrvanta.modules.integrations.infrastructure import models as _integration_models  # noqa: F401
from cyrvanta.shared.database import SessionFactory, tenant_session

_SOURCE = "test-alert-ordering"


async def _existing_tenant_id() -> UUID:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        return (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()


async def _seed(tenant_id: UUID) -> None:
    """One alert per severity, oldest being the most severe.

    That ordering is deliberate: sorting by recency has to put the newest
    first even though it is the least severe, and sorting by severity has to
    surface the oldest one -- otherwise a passing test could be explained by
    both sorts agreeing by accident.
    """
    base = datetime.now(UTC) - timedelta(hours=6)
    order = ["critical", "high", "medium", "low", "informational"]
    async with tenant_session(tenant_id) as session:
        for position, severity in enumerate(order):
            session.add(
                AlertReferenceModel(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    source=_SOURCE,
                    external_id=f"{_SOURCE}-{severity}",
                    observed_at=base + timedelta(minutes=position),
                    title=f"Alerta de prueba {severity}",
                    category="test",
                    severity=severity,
                    provenance="LIVE",
                    is_simulated=False,
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


def _ours(items: list) -> list:
    return [item for item in items if item.source == _SOURCE]


async def test_recent_is_the_default_and_severity_is_selectable() -> None:
    tenant_id = await _existing_tenant_id()
    await _cleanup(tenant_id)
    await _seed(tenant_id)
    try:
        service = IncidentService()

        recent = _ours(await service.list_alerts(tenant_id, limit=100, offset=0, search=_SOURCE))
        assert [item.severity for item in recent] == [
            "informational",
            "low",
            "medium",
            "high",
            "critical",
        ]

        by_severity = _ours(
            await service.list_alerts(
                tenant_id, limit=100, offset=0, search=_SOURCE, sort="severity"
            )
        )
        assert [item.severity for item in by_severity] == [
            "critical",
            "high",
            "medium",
            "low",
            "informational",
        ]
    finally:
        await _cleanup(tenant_id)


async def test_severity_sorts_by_rank_not_alphabetically() -> None:
    """Ordering by the stored word puts "critical" between "low" and "medium"."""
    assert sorted(SEVERITY_ORDER, key=lambda name: SEVERITY_ORDER[name], reverse=True) == [
        "critical",
        "high",
        "medium",
        "low",
        "informational",
    ]
    assert sorted(SEVERITY_ORDER) != [
        "critical",
        "high",
        "medium",
        "low",
        "informational",
    ]


async def test_severity_filter_narrows_to_what_was_asked() -> None:
    tenant_id = await _existing_tenant_id()
    await _cleanup(tenant_id)
    await _seed(tenant_id)
    try:
        service = IncidentService()

        urgent = _ours(
            await service.list_alerts(
                tenant_id,
                limit=100,
                offset=0,
                search=_SOURCE,
                severity=["critical", "high"],
            )
        )

        assert {item.severity for item in urgent} == {"critical", "high"}
        # An empty filter must not be read as "show nothing".
        assert len(_ours(await service.list_alerts(tenant_id, 100, 0, _SOURCE, "recent", []))) == 5
    finally:
        await _cleanup(tenant_id)
