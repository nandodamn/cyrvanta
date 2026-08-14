from uuid import UUID

from sqlalchemy import delete, text

from cyrvanta.modules.integrations.application.automatic_wazuh_ingestion import (
    AutomaticWazuhIngestionService,
)
from cyrvanta.modules.integrations.infrastructure.models import IntegrationSyncStateModel
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.database import SessionFactory, tenant_session


async def _existing_tenant_id() -> UUID:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        return (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()


async def _existing_integration_id(tenant_id: UUID) -> UUID:
    async with tenant_session(tenant_id) as session:
        return (
            await session.execute(
                text("SELECT id FROM integrations WHERE tenant_id = :tenant_id LIMIT 1"),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar()


async def test_synchronize_all_tenants_is_a_noop_when_wazuh_not_live(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "wazuh_mode", "disabled")
    service = AutomaticWazuhIngestionService(settings)

    synced = await service.synchronize_all_tenants()

    assert synced == 0


async def test_cursor_round_trips_through_persistence() -> None:
    tenant_id = await _existing_tenant_id()
    integration_id = await _existing_integration_id(tenant_id)
    service = AutomaticWazuhIngestionService(get_settings())

    try:
        assert await service._load_cursor(tenant_id, integration_id) is None

        await service._store_cursor(tenant_id, integration_id, "cursor-1")
        assert await service._load_cursor(tenant_id, integration_id) == "cursor-1"

        await service._store_cursor(tenant_id, integration_id, "cursor-2")
        assert await service._load_cursor(tenant_id, integration_id) == "cursor-2"
    finally:
        async with tenant_session(tenant_id) as session:
            await session.execute(
                delete(IntegrationSyncStateModel).where(
                    IntegrationSyncStateModel.tenant_id == tenant_id,
                    IntegrationSyncStateModel.integration_id == integration_id,
                )
            )
