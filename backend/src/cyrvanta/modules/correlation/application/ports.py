from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cyrvanta.modules.correlation.domain.models import (
    CorrelationCandidate,
    CorrelationMatch,
    CorrelationRule,
)


@dataclass(frozen=True, slots=True)
class ReservedMatch:
    match_id: UUID
    created: bool


class CorrelationRepository(Protocol):
    async def active_rules(self) -> tuple[CorrelationRule, ...]: ...

    async def candidate(self, revision_id: UUID) -> CorrelationCandidate | None: ...

    async def candidates(
        self, window_start: datetime, window_end: datetime, limit: int
    ) -> tuple[CorrelationCandidate, ...]: ...

    async def reserve_match(
        self,
        tenant_id: UUID,
        match: CorrelationMatch,
        trigger_revision_id: UUID,
    ) -> ReservedMatch: ...

    async def prior_incident(self, match_id: UUID, match: CorrelationMatch) -> UUID | None: ...

    async def attach_incident(self, match_id: UUID, incident_id: UUID) -> None: ...

    async def attach_claim(self, match_id: UUID, claim_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class IncidentCorrelationResult:
    incident_id: UUID
    created: bool


class IncidentCorrelationPort(Protocol):
    async def apply_match(
        self,
        *,
        tenant_id: UUID,
        match_id: UUID,
        match: CorrelationMatch,
        prior_incident_id: UUID | None,
        correlation_id: UUID,
    ) -> IncidentCorrelationResult: ...


class ClaimCorrelationPort(Protocol):
    async def record_match(
        self,
        *,
        tenant_id: UUID,
        incident_id: UUID,
        match_id: UUID,
        match: CorrelationMatch,
        correlation_id: UUID,
        causation_id: UUID,
    ) -> UUID: ...
