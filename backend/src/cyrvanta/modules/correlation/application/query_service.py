from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.correlation.application.schemas import (
    CorrelationFactorResponse,
    CorrelationMemberResponse,
    CorrelationResponse,
)
from cyrvanta.modules.correlation.infrastructure.models import (
    CorrelationFactorModel,
    CorrelationMemberModel,
)
from cyrvanta.modules.incident.infrastructure.models import (
    CorrelationRunModel,
    IncidentModel,
)
from cyrvanta.shared.database import tenant_session


class CorrelationNotFound(Exception):
    pass


class CorrelationQueryService:
    async def list_for_incident(
        self, tenant_id: UUID, incident_id: UUID, *, limit: int, offset: int
    ) -> list[CorrelationResponse]:
        async with tenant_session(tenant_id) as session:
            incident = await session.get(IncidentModel, incident_id)
            if incident is None:
                raise CorrelationNotFound
            matches = (
                await session.scalars(
                    select(CorrelationRunModel)
                    .where(CorrelationRunModel.incident_id == incident_id)
                    .order_by(
                        CorrelationRunModel.created_at.desc(),
                        CorrelationRunModel.id.desc(),
                    )
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            return [await self._view(session, match) for match in matches]

    async def get(self, tenant_id: UUID, match_id: UUID) -> CorrelationResponse:
        async with tenant_session(tenant_id) as session:
            match = await session.get(CorrelationRunModel, match_id)
            if match is None or match.incident_id is None:
                raise CorrelationNotFound
            return await self._view(session, match)

    @staticmethod
    async def _view(
        session: AsyncSession, match: CorrelationRunModel
    ) -> CorrelationResponse:
        if match.incident_id is None:
            raise CorrelationNotFound
        members = (
            await session.scalars(
                select(CorrelationMemberModel)
                .where(CorrelationMemberModel.correlation_run_id == match.id)
                .order_by(CorrelationMemberModel.sort_order)
            )
        ).all()
        factors = (
            await session.scalars(
                select(CorrelationFactorModel)
                .where(CorrelationFactorModel.correlation_run_id == match.id)
                .order_by(CorrelationFactorModel.factor_code)
            )
        ).all()
        return CorrelationResponse(
            id=match.id,
            incident_id=match.incident_id,
            rule_code=match.rule_code,
            rule_version=match.rule_version,
            score=match.score,
            threshold=match.threshold,
            result_type=match.result_type,
            explanation=match.explanation,
            is_simulated=match.is_simulated,
            window_start=match.window_start,
            window_end=match.window_end,
            claim_id=match.claim_id,
            created_at=match.created_at,
            members=[
                CorrelationMemberResponse.model_validate(member)
                for member in members
            ],
            factors=[
                CorrelationFactorResponse.model_validate(factor)
                for factor in factors
            ],
        )
