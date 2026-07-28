from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.correlation.application.ports import IncidentCorrelationResult
from cyrvanta.modules.correlation.domain.models import (
    ACTIVE_INCIDENT_STATES,
    CorrelationMatch,
)
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
from cyrvanta.modules.incident.infrastructure.models import (
    IncidentAlertModel,
    IncidentModel,
    IncidentTimelineModel,
)


def _severity(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 20:
        return "low"
    return "informational"


PRIORITY_BY_SEVERITY = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
    "informational": 5,
}


class IncidentCorrelationAdapter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def apply_match(
        self,
        *,
        tenant_id: UUID,
        match_id: UUID,
        match: CorrelationMatch,
        prior_incident_id: UUID | None,
        correlation_id: UUID,
    ) -> IncidentCorrelationResult:
        incident = None
        if prior_incident_id is not None:
            incident = await self._session.scalar(
                select(IncidentModel)
                .where(
                    IncidentModel.id == prior_incident_id,
                    IncidentModel.status.in_(ACTIVE_INCIDENT_STATES),
                )
                .with_for_update()
            )
        created = incident is None
        now = datetime.now(UTC)
        if incident is None:
            severity = _severity(max(member.severity_score for member in match.members))
            incident = IncidentModel(
                tenant_id=tenant_id,
                code=f"CORR-{uuid4().hex[:8].upper()}",
                title="Correlated security signals",
                description=(
                    f"Deterministic rule {match.rule_code} v{match.rule_version} "
                    f"matched {len(match.members)} canonical finding revisions."
                ),
                status="new",
                severity=severity,
                priority=PRIORITY_BY_SEVERITY[severity],
                classification=match.rule_code,
                version=1,
                is_simulated=match.is_simulated,
                detected_at=min(member.effective_at for member in match.members),
                updated_at=now,
            )
            self._session.add(incident)
            await self._session.flush()
        else:
            incident.version += 1
            incident.updated_at = now
            incident.is_simulated = incident.is_simulated or match.is_simulated

        for member in match.members:
            await self._session.execute(
                pg_insert(IncidentAlertModel)
                .values(
                    tenant_id=tenant_id,
                    incident_id=incident.id,
                    alert_id=member.finding_id,
                )
                .on_conflict_do_nothing(
                    index_elements=(
                        IncidentAlertModel.tenant_id,
                        IncidentAlertModel.incident_id,
                        IncidentAlertModel.alert_id,
                    )
                )
            )
        self._session.add(
            IncidentTimelineModel(
                tenant_id=tenant_id,
                incident_id=incident.id,
                actor_user_id=None,
                entry_type="correlated",
                summary=(
                    f"{match.rule_code} v{match.rule_version}: "
                    f"{len(match.members)} revisions, score {match.score}/100"
                ),
                resource_type="correlation_match",
                resource_id=match_id,
                incident_version=incident.version,
                effective_at=max(member.effective_at for member in match.members),
            )
        )
        self._session.add(
            AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=None,
                action="incident.correlation.applied",
                resource_type="incident",
                resource_id=incident.id,
                outcome="success",
                correlation_id=correlation_id,
                details={
                    "match_id": str(match_id),
                    "rule_code": match.rule_code,
                    "rule_version": match.rule_version,
                    "created": created,
                },
            )
        )
        await self._session.flush()
        return IncidentCorrelationResult(incident.id, created)
