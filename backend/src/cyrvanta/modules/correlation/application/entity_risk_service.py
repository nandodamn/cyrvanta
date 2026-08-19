"""Sweep for entities that are accumulating alarms, whatever those alarms are.

Rule correlation is triggered by a finding and asks whether it completes a
known pattern. Nothing until now asked the standing question: *is something
piling up on this host?* An attacker who never completes a pattern anyone
wrote down was invisible.

The sweep is stateless. It recomputes every score from the alarms inside the
window instead of maintaining a running total, so a score can always be
re-derived and shown to be right, and a bad deploy cannot leave a corrupted
counter behind.

It is **off by default** (`ENTITY_RISK_ENABLED`). Turning it on changes what
opens incidents in a live tenant, and the right threshold depends on how noisy
that estate actually is -- so the intended order is to look at real scores with
`python -m cyrvanta.preview_entity_risk` first, choose a threshold, and only
then enable it.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.correlation.domain.entity_risk import (
    DEFAULT_BASELINE_DAYS,
    DEFAULT_HALF_LIFE_HOURS,
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW_HOURS,
    EntityRisk,
    RiskObservation,
    score_all,
)
from cyrvanta.modules.correlation.domain.models import ACTIVE_INCIDENT_STATES
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, TenantModel
from cyrvanta.modules.incident.infrastructure.models import (
    AlertReferenceModel,
    IncidentAlertModel,
    IncidentModel,
    IncidentTimelineModel,
)
from cyrvanta.modules.integrations.infrastructure.models import FindingRevisionModel
from cyrvanta.shared.config import Settings
from cyrvanta.shared.database import SessionFactory, tenant_session

logger = logging.getLogger("cyrvanta.entity_risk")

# Configuration assessment re-reports the whole compliance posture on every
# scan. It is a report, not activity, and it would dominate any score.
EXCLUDED_CATEGORIES = frozenset({"sca"})
CLASSIFICATION = "entity-risk"


def _severity(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


PRIORITY_BY_SEVERITY = {"critical": 1, "high": 2, "medium": 3, "low": 4}


class EntityRiskService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def observations(
        self, tenant_id: UUID, *, window_hours: int = DEFAULT_WINDOW_HOURS
    ) -> tuple[tuple[RiskObservation, ...], dict[str, set[UUID]]]:
        """Alarms in the window, plus which alert each entity's evidence came
        from so an incident can point at real records rather than a number.
        """
        since = datetime.now(UTC) - timedelta(hours=window_hours)
        rows = (
            await self._session.execute(
                select(
                    FindingRevisionModel.entity_references,
                    FindingRevisionModel.source_system,
                    FindingRevisionModel.rule_reference,
                    FindingRevisionModel.severity_score,
                    FindingRevisionModel.effective_at,
                    FindingRevisionModel.title,
                    FindingRevisionModel.alert_reference_id,
                )
                .join(
                    AlertReferenceModel,
                    AlertReferenceModel.id == FindingRevisionModel.alert_reference_id,
                )
                .where(
                    FindingRevisionModel.tenant_id == tenant_id,
                    FindingRevisionModel.effective_at >= since,
                    # Already judged noise by a human, and never synthetic:
                    # a demo must not be able to manufacture suspicion.
                    AlertReferenceModel.triage_status != "DISCARDED",
                    AlertReferenceModel.is_simulated.is_(False),
                )
            )
        ).all()

        observations: list[RiskObservation] = []
        alerts_by_entity: dict[str, set[UUID]] = {}
        for entities, source, reference, severity, effective_at, title, alert_id in rows:
            for entity in entities or []:
                if not isinstance(entity, dict):
                    continue
                kind, value = entity.get("kind"), entity.get("value")
                if not isinstance(kind, str) or not isinstance(value, str) or not value:
                    continue
                namespace = entity.get("namespace")
                key = f"{kind}|{namespace if isinstance(namespace, str) else ''}|{value}"
                observations.append(
                    RiskObservation(
                        entity_key=key,
                        signal_key=f"{source}:{reference or 'unknown'}",
                        title=title,
                        severity_score=severity,
                        effective_at=effective_at,
                    )
                )
                alerts_by_entity.setdefault(key, set()).add(alert_id)
        return tuple(observations), alerts_by_entity

    async def baseline(
        self, tenant_id: UUID, *, window_hours: int, baseline_days: int
    ) -> frozenset[tuple[str, str]]:
        """Which (entity, signal) pairs this estate already produced before the
        scoring window -- in other words, what is normal here.

        Read from the same alarms rather than a learned model, so "normal" is
        auditable: it is exactly what this entity has been seen doing.
        """
        now = datetime.now(UTC)
        until = now - timedelta(hours=window_hours)
        since = now - timedelta(days=baseline_days)
        rows = (
            await self._session.execute(
                select(
                    FindingRevisionModel.entity_references,
                    FindingRevisionModel.source_system,
                    FindingRevisionModel.rule_reference,
                )
                .join(
                    AlertReferenceModel,
                    AlertReferenceModel.id == FindingRevisionModel.alert_reference_id,
                )
                .where(
                    FindingRevisionModel.tenant_id == tenant_id,
                    FindingRevisionModel.effective_at >= since,
                    FindingRevisionModel.effective_at < until,
                    AlertReferenceModel.is_simulated.is_(False),
                )
            )
        ).all()
        known: set[tuple[str, str]] = set()
        for entities, source, reference in rows:
            signal = f"{source}:{reference or 'unknown'}"
            for entity in entities or []:
                if not isinstance(entity, dict):
                    continue
                kind, value = entity.get("kind"), entity.get("value")
                if not isinstance(kind, str) or not isinstance(value, str) or not value:
                    continue
                namespace = entity.get("namespace")
                key = f"{kind}|{namespace if isinstance(namespace, str) else ''}|{value}"
                known.add((key, signal))
        return frozenset(known)

    async def evaluate(
        self,
        tenant_id: UUID,
        *,
        threshold: int = DEFAULT_THRESHOLD,
        window_hours: int = DEFAULT_WINDOW_HOURS,
        half_life_hours: float = DEFAULT_HALF_LIFE_HOURS,
        baseline_days: int = DEFAULT_BASELINE_DAYS,
    ) -> tuple[tuple[EntityRisk, ...], dict[str, set[UUID]]]:
        observations, alerts = await self.observations(tenant_id, window_hours=window_hours)
        excluded = tuple(
            item
            for item in observations
            if item.signal_key.split(":", 1)[0] not in EXCLUDED_CATEGORIES
        )
        known = await self.baseline(
            tenant_id, window_hours=window_hours, baseline_days=baseline_days
        )
        return (
            score_all(
                excluded,
                now=datetime.now(UTC),
                threshold=threshold,
                window_hours=window_hours,
                half_life_hours=half_life_hours,
                baseline=known,
            ),
            alerts,
        )

    async def sweep(
        self,
        tenant_id: UUID,
        *,
        threshold: int = DEFAULT_THRESHOLD,
        window_hours: int = DEFAULT_WINDOW_HOURS,
        half_life_hours: float = DEFAULT_HALF_LIFE_HOURS,
        baseline_days: int = DEFAULT_BASELINE_DAYS,
    ) -> tuple[UUID, ...]:
        scored, alerts = await self.evaluate(
            tenant_id,
            threshold=threshold,
            window_hours=window_hours,
            half_life_hours=half_life_hours,
            baseline_days=baseline_days,
        )
        touched: list[UUID] = []
        for risk in scored:
            if not risk.is_suspicious:
                continue
            incident_id = await self._apply(tenant_id, risk, alerts.get(risk.entity_key, set()))
            if incident_id is not None:
                touched.append(incident_id)
        return tuple(touched)

    async def _apply(self, tenant_id: UUID, risk: EntityRisk, alert_ids: set[UUID]) -> UUID | None:
        if not alert_ids:
            return None
        # If this evidence already belongs to an open incident -- whichever
        # rule opened it -- this is the same story told twice. Attach to it
        # instead of raising a parallel incident about the same host.
        existing = await self._session.scalar(
            select(IncidentModel.id)
            .join(IncidentAlertModel, IncidentAlertModel.incident_id == IncidentModel.id)
            .where(
                IncidentModel.tenant_id == tenant_id,
                IncidentModel.status.in_(ACTIVE_INCIDENT_STATES),
                IncidentAlertModel.alert_id.in_(alert_ids),
            )
            .order_by(IncidentModel.created_at.desc())
            .limit(1)
        )

        now = datetime.now(UTC)
        created = existing is None
        if existing is None:
            severity = _severity(risk.score)
            incident = IncidentModel(
                tenant_id=tenant_id,
                code=f"RISK-{uuid4().hex[:8].upper()}",
                title="Concentrated suspicious activity",
                description=(
                    f"{risk.distinct_signals} distinct signals on {risk.entity_key} "
                    f"scored {risk.score}/{risk.threshold} in the last "
                    f"{round((risk.window_end - risk.window_start).total_seconds() / 3600)}h."
                ),
                status="new",
                severity=severity,
                priority=PRIORITY_BY_SEVERITY[severity],
                classification=CLASSIFICATION,
                version=1,
                is_simulated=False,
                detected_at=min(item.most_recent for item in risk.contributions),
                updated_at=now,
            )
            self._session.add(incident)
            await self._session.flush()
            incident_id = incident.id
            version = incident.version
        else:
            attached = await self._session.get(IncidentModel, existing)
            if attached is None:
                return None
            attached.version += 1
            attached.updated_at = now
            incident_id = attached.id
            version = attached.version

        for alert_id in sorted(alert_ids):
            await self._session.execute(
                pg_insert(IncidentAlertModel)
                .values(tenant_id=tenant_id, incident_id=incident_id, alert_id=alert_id)
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
                incident_id=incident_id,
                actor_user_id=None,
                entry_type="correlated",
                summary=(
                    f"entity risk {risk.score}/{risk.threshold} on {risk.entity_key}: "
                    + ", ".join(
                        f"{item.signal_key} x{item.occurrences}" for item in risk.contributions[:6]
                    )
                ),
                resource_type="entity_risk",
                resource_id=None,
                incident_version=version,
                effective_at=max(item.most_recent for item in risk.contributions),
            )
        )
        self._session.add(
            AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=None,
                action="incident.entity_risk.applied",
                resource_type="incident",
                resource_id=incident_id,
                outcome="success",
                correlation_id=uuid4(),
                details={
                    "entity_key": risk.entity_key,
                    "score": risk.score,
                    "threshold": risk.threshold,
                    "distinct_signals": risk.distinct_signals,
                    "fingerprint": risk.fingerprint,
                    "created": created,
                },
            )
        )
        await self._session.flush()
        return incident_id


async def sweep_all_tenants(settings: Settings) -> int:
    """One sweep across every active tenant. Returns tenants where the sweep
    touched an incident.

    A failure on one tenant must not stop the others: this runs unattended, and
    a single misbehaving estate silently disabling detection everywhere else
    would be worse than the original blindness.
    """
    if not settings.entity_risk_enabled:
        return 0
    async with SessionFactory() as session:
        tenant_ids = list(
            (
                await session.scalars(
                    select(TenantModel.id)
                    .where(TenantModel.status == "active")
                    .order_by(TenantModel.created_at)
                )
            ).all()
        )
    touched = 0
    for tenant_id in tenant_ids:
        try:
            async with tenant_session(tenant_id) as session:
                incidents = await EntityRiskService(session).sweep(
                    tenant_id,
                    threshold=settings.entity_risk_threshold,
                    window_hours=settings.entity_risk_window_hours,
                    half_life_hours=settings.entity_risk_half_life_hours,
                    baseline_days=settings.entity_risk_baseline_days,
                )
        except Exception:
            logger.exception("entity_risk_sweep_failed", extra={"tenant_id": str(tenant_id)})
            continue
        if incidents:
            touched += 1
    return touched
