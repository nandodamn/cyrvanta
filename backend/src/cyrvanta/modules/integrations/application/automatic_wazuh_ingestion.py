import logging
from uuid import UUID, uuid4

from sqlalchemy import select

from cyrvanta.modules.identity.infrastructure.models import TenantModel
from cyrvanta.modules.integrations.application.connection_service import (
    IntegrationConfigurationError,
)
from cyrvanta.modules.integrations.application.finding_ingestion import (
    FindingIngestionService,
)
from cyrvanta.modules.integrations.application.services.synchronization import (
    FindingSynchronizationService,
)
from cyrvanta.modules.integrations.domain.errors import UnsupportedCapabilityError
from cyrvanta.modules.integrations.domain.findings import CanonicalFinding
from cyrvanta.modules.integrations.infrastructure.composition import (
    configured_wazuh_connection,
)
from cyrvanta.modules.integrations.infrastructure.finding_repository import (
    SqlFindingRepository,
)
from cyrvanta.modules.integrations.infrastructure.models import IntegrationSyncStateModel
from cyrvanta.shared.config import Settings
from cyrvanta.shared.database import SessionFactory, tenant_session
from cyrvanta.shared.infrastructure.event_store import SqlEventStore

_STREAM_TYPE = "wazuh_findings"

logger = logging.getLogger("cyrvanta.integrations.automatic_wazuh_ingestion")


class AutomaticWazuhIngestionService:
    """PHASE_25: tenant-scoped, cursor-based replacement for the manual
    sync_wazuh_findings CLI. Reuses FindingSynchronizationService /
    FindingIngestionService unchanged -- this only adds the periodic,
    multi-tenant driving loop and cursor persistence.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.event_store = SqlEventStore(SessionFactory, settings.event_max_payload_bytes)

    async def synchronize_all_tenants(self, *, limit: int = 100) -> int:
        if self.settings.wazuh_mode != "live" or self.settings.opensearch_mode != "live":
            return 0
        async with SessionFactory() as session:
            tenant_ids = list(
                (
                    await session.scalars(
                        select(TenantModel.id)
                        .where(TenantModel.status == "active")
                        .order_by(TenantModel.created_at)
                    )
                ).all()
            )
        synced_tenants = 0
        for tenant_id in tenant_ids:
            try:
                created = await self._synchronize_tenant(tenant_id, limit=limit)
            except (IntegrationConfigurationError, UnsupportedCapabilityError):
                continue
            except Exception:
                logger.exception(
                    "wazuh_ingestion_tenant_failed", extra={"tenant_id": str(tenant_id)}
                )
                continue
            if created:
                synced_tenants += 1
        return synced_tenants

    async def _synchronize_tenant(self, tenant_id: UUID, *, limit: int) -> int:
        integration_id, connector = await configured_wazuh_connection(tenant_id)
        cursor = await self._load_cursor(tenant_id, integration_id)
        correlation_id = uuid4()
        created = 0

        async def sink(finding: CanonicalFinding, _idempotency_key: str) -> None:
            nonlocal created
            async with tenant_session(tenant_id) as session:
                result = await FindingIngestionService(
                    SqlFindingRepository(session),
                    self.event_store.recorder(session),
                ).ingest(finding, correlation_id=correlation_id)
            if result.created:
                created += 1

        batch = await FindingSynchronizationService(connector, sink).synchronize(
            tenant_id, integration_id, cursor=cursor, limit=limit
        )
        if batch.next_cursor is not None and batch.next_cursor != cursor:
            await self._store_cursor(tenant_id, integration_id, batch.next_cursor)
        if created:
            logger.info(
                "wazuh_ingestion_batch_synchronized",
                extra={
                    "tenant_id": str(tenant_id),
                    "created": created,
                    "received": len(batch.items),
                    "correlation_id": str(correlation_id),
                },
            )
        return created

    async def _load_cursor(self, tenant_id: UUID, integration_id: UUID) -> str | None:
        async with tenant_session(tenant_id) as session:
            return await session.scalar(
                select(IntegrationSyncStateModel.cursor).where(
                    IntegrationSyncStateModel.tenant_id == tenant_id,
                    IntegrationSyncStateModel.integration_id == integration_id,
                    IntegrationSyncStateModel.stream_type == _STREAM_TYPE,
                )
            )

    async def _store_cursor(self, tenant_id: UUID, integration_id: UUID, cursor: str) -> None:
        async with tenant_session(tenant_id) as session:
            state = await session.scalar(
                select(IntegrationSyncStateModel).where(
                    IntegrationSyncStateModel.tenant_id == tenant_id,
                    IntegrationSyncStateModel.integration_id == integration_id,
                    IntegrationSyncStateModel.stream_type == _STREAM_TYPE,
                )
            )
            if state is None:
                session.add(
                    IntegrationSyncStateModel(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        integration_id=integration_id,
                        stream_type=_STREAM_TYPE,
                        cursor=cursor,
                    )
                )
            else:
                state.cursor = cursor
            await session.flush()
