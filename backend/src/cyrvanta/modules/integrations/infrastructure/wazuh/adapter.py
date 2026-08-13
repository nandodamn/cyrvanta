import asyncio
import json
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID

from cyrvanta.modules.integrations.application.ports.siem_connector import (
    SIEMConnectorPort,
)
from cyrvanta.modules.integrations.domain.errors import (
    ConnectorErrorCode,
    UnsupportedCapabilityError,
)
from cyrvanta.modules.integrations.domain.models import (
    CanonicalEventQuery,
    CanonicalEvidence,
    ConnectorCapabilities,
    ConnectorHealth,
    ConnectorStatus,
    EventSearchResult,
    ExternalEvidenceReference,
    ExternalIncidentBatch,
    FindingBatch,
)
from cyrvanta.modules.integrations.infrastructure.wazuh.client import WazuhIndexerClient
from cyrvanta.modules.integrations.infrastructure.wazuh.config import (
    WazuhConnectorConfigV1,
)
from cyrvanta.modules.integrations.infrastructure.wazuh.normalizer import WazuhNormalizer


class WazuhSIEMAdapter(SIEMConnectorPort):
    ADAPTER_VERSION = "1.0"

    def __init__(
        self,
        configuration: WazuhConnectorConfigV1,
        source_instance_id: UUID,
        *,
        indexer_username: str | None = None,
        indexer_password: str | None = None,
        indexer_bearer_token: str | None = None,
    ) -> None:
        self.configuration = configuration
        self.source_instance_id = source_instance_id
        self.client = WazuhIndexerClient(
            configuration,
            username=indexer_username,
            password=indexer_password,
            bearer_token=indexer_bearer_token,
        )
        self.normalizer = WazuhNormalizer()

    async def health_check(self) -> ConnectorHealth:
        started = monotonic()
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.configuration.manager_host, self.configuration.manager_port
                ),
                timeout=self.configuration.timeout_seconds,
            )
            writer.close()
            await writer.wait_closed()
            return ConnectorHealth(
                status=ConnectorStatus.HEALTHY,
                latency_ms=round((monotonic() - started) * 1000),
                detail="connector reachable",
                checked_at=datetime.now(UTC),
            )
        except (OSError, TimeoutError):
            return ConnectorHealth(
                status=ConnectorStatus.UNAVAILABLE,
                latency_ms=round((monotonic() - started) * 1000),
                error_code=ConnectorErrorCode.CONNECTOR_UNAVAILABLE.value,
                detail="connector unavailable",
                checked_at=datetime.now(UTC),
            )

    async def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            supports_alert_polling=True,
            supports_event_search=True,
            supports_raw_event_retrieval=False,
            supports_response_actions=False,
        )

    async def fetch_findings(
        self,
        tenant_id: UUID,
        cursor: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> FindingBatch:
        result = await self.client.search_alerts(cursor, start_time, end_time, limit)
        findings = [
            self.normalizer.normalize(hit, tenant_id, self.source_instance_id)
            for hit in result.hits
        ]
        next_cursor = (
            json.dumps(result.hits[-1].sort, separators=(",", ":"))
            if result.hits and result.hits[-1].sort
            else None
        )
        watermark = max((finding.occurred_at for finding in findings), default=None)
        return FindingBatch(items=findings, next_cursor=next_cursor, watermark=watermark)

    async def fetch_incidents(
        self,
        tenant_id: UUID,
        cursor: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> ExternalIncidentBatch:
        raise UnsupportedCapabilityError("supports_incident_polling")

    async def search_events(self, tenant_id: UUID, query: CanonicalEventQuery) -> EventSearchResult:
        source = await self.client.search_alerts(
            None,
            query.start_time,
            query.end_time,
            query.limit,
            query_text=query.text,
        )
        return EventSearchResult(
            findings=[
                self.normalizer.normalize(hit, tenant_id, self.source_instance_id)
                for hit in source.hits
            ]
        )

    async def get_evidence(
        self, tenant_id: UUID, reference: ExternalEvidenceReference
    ) -> CanonicalEvidence:
        raise UnsupportedCapabilityError("supports_raw_event_retrieval")

    async def acknowledge_external_incident(
        self, tenant_id: UUID, external_incident_id: str
    ) -> None:
        raise UnsupportedCapabilityError("supports_acknowledgement")

    async def close_external_incident(
        self, tenant_id: UUID, external_incident_id: str, resolution: str
    ) -> None:
        raise UnsupportedCapabilityError("supports_incident_closure")
