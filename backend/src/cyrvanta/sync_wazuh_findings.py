import argparse
import asyncio
import json
from uuid import UUID, uuid4

from cyrvanta.modules.integrations.application.finding_ingestion import (
    FindingIngestionService,
)
from cyrvanta.modules.integrations.application.services.synchronization import (
    FindingSynchronizationService,
)
from cyrvanta.modules.integrations.domain.findings import CanonicalFinding
from cyrvanta.modules.integrations.infrastructure.composition import (
    configured_wazuh_connector,
    configured_wazuh_integration_id,
)
from cyrvanta.modules.integrations.infrastructure.finding_repository import (
    SqlFindingRepository,
)
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.database import SessionFactory, tenant_session
from cyrvanta.shared.infrastructure.event_store import SqlEventStore


async def synchronize(tenant_id: UUID, limit: int, cursor: str | None) -> None:
    settings = get_settings()
    integration_id = configured_wazuh_integration_id(tenant_id)
    connector = configured_wazuh_connector(tenant_id)
    correlation_id = uuid4()
    event_store = SqlEventStore(SessionFactory, settings.event_max_payload_bytes)
    created = 0
    duplicates = 0

    async def sink(finding: CanonicalFinding, _idempotency_key: str) -> None:
        nonlocal created, duplicates
        async with tenant_session(tenant_id) as session:
            result = await FindingIngestionService(
                SqlFindingRepository(session),
                event_store.recorder(session),
            ).ingest(finding, correlation_id=correlation_id)
        if result.created:
            created += 1
        else:
            duplicates += 1

    batch = await FindingSynchronizationService(connector, sink).synchronize(
        tenant_id,
        integration_id,
        cursor=cursor,
        limit=limit,
    )
    print(
        json.dumps(
            {
                "received": len(batch.items),
                "created": created,
                "duplicates": duplicates,
                "next_cursor": batch.next_cursor,
                "watermark": (
                    batch.watermark.isoformat() if batch.watermark is not None else None
                ),
                "correlation_id": str(correlation_id),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize one bounded batch of real Wazuh findings."
    )
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--limit", type=int, default=100, choices=range(1, 501))
    parser.add_argument("--cursor")
    arguments = parser.parse_args()
    asyncio.run(synchronize(arguments.tenant_id, arguments.limit, arguments.cursor))


if __name__ == "__main__":
    main()
