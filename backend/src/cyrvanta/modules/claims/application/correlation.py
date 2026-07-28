from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.claims.application.service import ClaimService
from cyrvanta.modules.correlation.domain.models import CorrelationMatch


class ClaimCorrelationAdapter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._service = ClaimService()

    async def record_match(
        self,
        *,
        tenant_id: UUID,
        incident_id: UUID,
        match_id: UUID,
        match: CorrelationMatch,
        correlation_id: UUID,
        causation_id: UUID,
    ) -> UUID:
        return await self._service.record_correlation_match(
            self._session,
            tenant_id=tenant_id,
            incident_id=incident_id,
            match_id=match_id,
            rule_code=match.rule_code,
            rule_version=match.rule_version,
            score=match.score,
            input_fingerprint=match.input_fingerprint,
            revision_ids=tuple(member.revision_id for member in match.members),
            is_simulated=match.is_simulated,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
