import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text

import cyrvanta.modules.identity.infrastructure.models  # noqa
import cyrvanta.modules.incident.infrastructure.models  # noqa
import cyrvanta.modules.integrations.infrastructure.models  # noqa
import cyrvanta.modules.threat_knowledge.infrastructure.models  # noqa
from cyrvanta.modules.incident.application.schemas import AlertTriageUpdate
from cyrvanta.modules.incident.application.service import IncidentService
from cyrvanta.modules.incident.infrastructure.models import AlertReferenceModel
from cyrvanta.shared.database import SessionFactory


async def test_alert_triage_flow():
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        tenant_row = await session.execute(text("SELECT id FROM tenants LIMIT 1"))
        tenant_id = tenant_row.scalar()
        user_row = await session.execute(text("SELECT id FROM users LIMIT 1"))
        actor_id = user_row.scalar()
        await session.execute(
            text(f"SELECT set_config('app.current_tenant_id', '{tenant_id}', true)")
        )

        alert = AlertReferenceModel(
            tenant_id=tenant_id,
            source="test-source",
            external_id=f"ext-triage-{uuid4().hex[:6]}",
            observed_at=datetime.now(UTC),
            title="Test Triage Alert",
            category="test",
            severity="medium",
            provenance="unit-test",
        )
        session.add(alert)
        await session.flush()
        alert_id = alert.id

    service = IncidentService()
    res = await service.triage_alert(
        tenant_id=tenant_id,
        actor_id=actor_id,
        alert_id=alert_id,
        payload=AlertTriageUpdate(triage_status="DISCARDED"),
        correlation_id=uuid4(),
    )

    assert res.id == alert_id
    assert res.triage_status == "DISCARDED"
    assert res.reviewed_by_user_id == actor_id
    assert res.reviewed_at is not None
    print("ALERT_TRIAGE_TEST_PASSED_SUCCESSFULLY")


if __name__ == "__main__":
    asyncio.run(test_alert_triage_flow())
