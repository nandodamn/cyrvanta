from datetime import UTC, datetime
from uuid import UUID

from cyrvanta.modules.integrations.application.ports.siem_connector import (
    SIEMConnectorPort,
)
from cyrvanta.modules.integrations.domain.errors import UnsupportedCapabilityError
from cyrvanta.modules.integrations.domain.models import (
    CanonicalEventQuery,
    CanonicalEvidence,
    CanonicalFinding,
    ConnectorCapabilities,
    ConnectorHealth,
    ConnectorStatus,
    EventSearchResult,
    ExternalEvidenceReference,
    ExternalIncidentBatch,
    FindingBatch,
)


class FakeSIEMConnector(SIEMConnectorPort):
    """Test-only connector. Production composition never registers this class."""

    def __init__(
        self,
        findings: list[CanonicalFinding] | None = None,
        capabilities: ConnectorCapabilities | None = None,
    ) -> None:
        self.findings = findings or []
        self.capabilities = capabilities or ConnectorCapabilities(
            supports_alert_polling=True,
            supports_event_search=True,
        )

    async def health_check(self) -> ConnectorHealth:
        return ConnectorHealth(status=ConnectorStatus.HEALTHY, checked_at=datetime.now(UTC))

    async def get_capabilities(self) -> ConnectorCapabilities:
        return self.capabilities

    async def fetch_findings(
        self,
        tenant_id: UUID,
        cursor: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> FindingBatch:
        items = [item for item in self.findings if item.tenant_id == tenant_id][:limit]
        return FindingBatch(items=items, next_cursor=None)

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
        return EventSearchResult(
            findings=[item for item in self.findings if item.tenant_id == tenant_id][: query.limit]
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
