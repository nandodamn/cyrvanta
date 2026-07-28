from collections.abc import Awaitable, Callable
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from cyrvanta.modules.integrations.application.ports.siem_connector import (
    SIEMConnectorPort,
)
from cyrvanta.modules.integrations.domain.errors import UnsupportedCapabilityError
from cyrvanta.modules.integrations.domain.models import CanonicalFinding, FindingBatch

FindingSink = Callable[[CanonicalFinding, str], Awaitable[None]]


def finding_idempotency_key(integration_id: UUID, finding: CanonicalFinding) -> str:
    material = "|".join(
        (
            str(finding.tenant_id),
            str(integration_id),
            finding.source_object_type,
            finding.source_object_id,
            finding.payload_fingerprint,
        )
    )
    return sha256(material.encode()).hexdigest()


class FindingSynchronizationService:
    def __init__(self, connector: SIEMConnectorPort, sink: FindingSink) -> None:
        self.connector = connector
        self.sink = sink

    async def synchronize(
        self,
        tenant_id: UUID,
        integration_id: UUID,
        cursor: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> FindingBatch:
        capabilities = await self.connector.get_capabilities()
        if not capabilities.supports_alert_polling:
            raise UnsupportedCapabilityError("supports_alert_polling")
        batch = await self.connector.fetch_findings(tenant_id, cursor, start_time, end_time, limit)
        seen_keys: set[str] = set()
        for finding in batch.items:
            if finding.tenant_id != tenant_id:
                raise ValueError("Connector returned a finding outside the tenant scope")
            if finding.integration_id != integration_id:
                raise ValueError("Connector returned a finding for another integration")
            idempotency_key = finding_idempotency_key(integration_id, finding)
            if idempotency_key in seen_keys:
                continue
            seen_keys.add(idempotency_key)
            await self.sink(finding, idempotency_key)
        return batch
