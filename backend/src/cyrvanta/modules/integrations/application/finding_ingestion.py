from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cyrvanta.modules.integrations.domain.findings import CanonicalFinding
from cyrvanta.shared.application.messaging import EventRecorder
from cyrvanta.shared.domain.events import DomainEvent

FINDING_NORMALIZED_EVENT = "security.finding.normalized"


@dataclass(frozen=True, slots=True)
class PersistedFinding:
    finding_id: UUID
    revision_id: UUID
    revision_number: int
    created: bool


class FindingRepository(Protocol):
    async def persist(self, finding: CanonicalFinding) -> PersistedFinding: ...


class FindingIngestionService:
    def __init__(
        self,
        repository: FindingRepository,
        event_recorder: EventRecorder,
    ) -> None:
        self._repository = repository
        self._event_recorder = event_recorder

    async def ingest(
        self,
        finding: CanonicalFinding,
        *,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> PersistedFinding:
        persisted = await self._repository.persist(finding)
        if not persisted.created:
            return persisted
        await self._event_recorder.add(
            DomainEvent.create(
                event_name=FINDING_NORMALIZED_EVENT,
                tenant_id=finding.tenant_id,
                aggregate_type="security_finding",
                aggregate_id=persisted.finding_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                producer="security_integrations",
                occurred_at=finding.observed_at,
                payload={
                    "finding_id": str(persisted.finding_id),
                    "revision_id": str(persisted.revision_id),
                    "revision_number": persisted.revision_number,
                    "integration_id": str(finding.integration_id),
                    "source_system": finding.source_system,
                    "severity_score": finding.severity_score,
                    "effective_at": finding.effective_at.isoformat(),
                    "normalization_status": finding.normalization.status.value,
                },
            )
        )
        return persisted
