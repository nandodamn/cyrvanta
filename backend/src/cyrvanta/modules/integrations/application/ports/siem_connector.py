from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from cyrvanta.modules.integrations.domain.models import (
    CanonicalEventQuery,
    CanonicalEvidence,
    ConnectorCapabilities,
    ConnectorHealth,
    EventSearchResult,
    ExternalEvidenceReference,
    ExternalIncidentBatch,
    FindingBatch,
)


class SIEMConnectorPort(ABC):
    @abstractmethod
    async def health_check(self) -> ConnectorHealth: ...

    @abstractmethod
    async def get_capabilities(self) -> ConnectorCapabilities: ...

    @abstractmethod
    async def fetch_findings(
        self,
        tenant_id: UUID,
        cursor: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> FindingBatch: ...

    @abstractmethod
    async def fetch_incidents(
        self,
        tenant_id: UUID,
        cursor: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> ExternalIncidentBatch: ...

    @abstractmethod
    async def search_events(
        self, tenant_id: UUID, query: CanonicalEventQuery
    ) -> EventSearchResult: ...

    @abstractmethod
    async def get_evidence(
        self, tenant_id: UUID, reference: ExternalEvidenceReference
    ) -> CanonicalEvidence: ...

    @abstractmethod
    async def acknowledge_external_incident(
        self, tenant_id: UUID, external_incident_id: str
    ) -> None: ...

    @abstractmethod
    async def close_external_incident(
        self, tenant_id: UUID, external_incident_id: str, resolution: str
    ) -> None: ...

