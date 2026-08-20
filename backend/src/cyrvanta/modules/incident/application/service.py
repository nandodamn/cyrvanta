from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, UserModel
from cyrvanta.modules.incident.application.schemas import (
    AlertResponse,
    AlertTriageUpdate,
    IncidentAssign,
    IncidentCreate,
    IncidentTransition,
    IncidentUpdate,
    Severity,
    TimelineCreate,
)
from cyrvanta.modules.incident.infrastructure.models import (
    AlertReferenceModel,
    IncidentAlertModel,
    IncidentModel,
    IncidentTimelineModel,
)
from cyrvanta.shared.database import tenant_session


class IncidentNotFound(Exception):
    pass


class IncidentConflict(Exception):
    pass


class InvalidTransition(Exception):
    pass


TRANSITIONS: dict[str, set[str]] = {
    "new": {"triaged", "closed"},
    "triaged": {"investigating", "closed"},
    "investigating": {"contained", "resolved", "closed"},
    "contained": {"investigating", "resolved"},
    "resolved": {"closed", "reopened"},
    "closed": {"reopened"},
    "reopened": {"investigating", "contained", "resolved", "closed"},
}

AlertSort = Literal["recent", "severity"]

# Severity is stored as a word, so ordering by the column sorts alphabetically:
# "critical" would land between "low" and "medium". Rank it explicitly instead.
SEVERITY_ORDER: dict[str, int] = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "informational": 1,
}
SEVERITY_RANK = case(
    SEVERITY_ORDER,
    value=AlertReferenceModel.severity,
    else_=0,
)


class IncidentService:
    async def list_alerts(
        self,
        tenant_id: UUID,
        limit: int,
        offset: int = 0,
        search: str | None = None,
        sort: AlertSort = "recent",
        severity: Sequence[Severity] | None = None,
    ) -> list[AlertResponse]:
        async with tenant_session(tenant_id) as session:
            statement = (
                select(AlertReferenceModel, UserModel.email, UserModel.display_name)
                .outerjoin(
                    UserModel,
                    AlertReferenceModel.reviewed_by_user_id == UserModel.id,
                )
                .where(AlertReferenceModel.is_simulated.is_(False))
            )
            if pattern := self._search_pattern(search):
                statement = statement.where(
                    or_(
                        AlertReferenceModel.title.ilike(pattern, escape="\\"),
                        AlertReferenceModel.source.ilike(pattern, escape="\\"),
                        AlertReferenceModel.category.ilike(pattern, escape="\\"),
                        AlertReferenceModel.external_id.ilike(pattern, escape="\\"),
                    )
                )
            if severity:
                statement = statement.where(AlertReferenceModel.severity.in_(list(severity)))
            # Newest first is the right default for a feed, but it buries a
            # critical alert under any volume of routine ones, so severity is
            # orderable too. Both break ties on the other key: equal severity
            # reads newest first, and equal timestamps read most severe first.
            order = (
                (SEVERITY_RANK.desc(), AlertReferenceModel.observed_at.desc())
                if sort == "severity"
                else (AlertReferenceModel.observed_at.desc(), SEVERITY_RANK.desc())
            )
            rows = (
                await session.execute(
                    statement.order_by(*order, AlertReferenceModel.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            result: list[AlertResponse] = []
            for alert, email, display_name in rows:
                dto = AlertResponse.model_validate(alert)
                dto.reviewer_display_name = display_name or email
                result.append(dto)
            return result

    async def get_alert(self, tenant_id: UUID, alert_id: UUID) -> AlertResponse:
        async with tenant_session(tenant_id) as session:
            row = (
                await session.execute(
                    select(AlertReferenceModel, UserModel.email, UserModel.display_name)
                    .outerjoin(UserModel, AlertReferenceModel.reviewed_by_user_id == UserModel.id)
                    .where(
                        AlertReferenceModel.id == alert_id,
                        AlertReferenceModel.is_simulated.is_(False),
                    )
                )
            ).first()
            if row is None:
                raise IncidentNotFound
            alert, email, display_name = row
            dto = AlertResponse.model_validate(alert)
            dto.reviewer_display_name = display_name or email
            return dto

    async def list_incident_alerts(self, tenant_id: UUID, incident_id: UUID) -> list[AlertResponse]:
        async with tenant_session(tenant_id) as session:
            await self._get(session, incident_id)
            statement = (
                select(AlertReferenceModel, UserModel.email, UserModel.display_name)
                .join(
                    IncidentAlertModel,
                    AlertReferenceModel.id == IncidentAlertModel.alert_id,
                )
                .outerjoin(UserModel, AlertReferenceModel.reviewed_by_user_id == UserModel.id)
                .where(
                    IncidentAlertModel.incident_id == incident_id,
                    AlertReferenceModel.is_simulated.is_(False),
                )
                .order_by(
                    AlertReferenceModel.observed_at.desc(),
                    AlertReferenceModel.id.desc(),
                )
            )
            rows = (await session.execute(statement)).all()
            result: list[AlertResponse] = []
            for alert, email, display_name in rows:
                dto = AlertResponse.model_validate(alert)
                dto.reviewer_display_name = display_name or email
                result.append(dto)
            return result

    async def triage_alert(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        alert_id: UUID,
        payload: AlertTriageUpdate,
        correlation_id: UUID,
    ) -> AlertResponse:
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            alert = await session.scalar(
                select(AlertReferenceModel).where(
                    AlertReferenceModel.id == alert_id,
                    AlertReferenceModel.is_simulated.is_(False),
                )
            )
            if alert is None:
                raise IncidentNotFound

            user_exists = await session.scalar(select(UserModel.id).where(UserModel.id == actor_id))
            effective_actor_id = actor_id if user_exists is not None else None

            alert.triage_status = payload.triage_status
            alert.reviewed_by_user_id = effective_actor_id
            alert.reviewed_at = now
            alert.updated_at = now
            if effective_actor_id is not None:
                self._audit(
                    session,
                    tenant_id,
                    effective_actor_id,
                    "alert.triage.updated",
                    alert.id,
                    correlation_id,
                )
            await session.flush()
        return await self.get_alert(tenant_id, alert_id)

    async def list_incidents(
        self, tenant_id: UUID, limit: int, offset: int = 0, search: str | None = None
    ) -> list[IncidentModel]:
        async with tenant_session(tenant_id) as session:
            statement = select(IncidentModel).where(IncidentModel.is_simulated.is_(False))
            if pattern := self._search_pattern(search):
                statement = statement.where(
                    or_(
                        IncidentModel.code.ilike(pattern, escape="\\"),
                        IncidentModel.title.ilike(pattern, escape="\\"),
                        IncidentModel.classification.ilike(pattern, escape="\\"),
                        IncidentModel.status.ilike(pattern, escape="\\"),
                        IncidentModel.severity.ilike(pattern, escape="\\"),
                    )
                )
            return list(
                (
                    await session.scalars(
                        statement.order_by(IncidentModel.updated_at.desc(), IncidentModel.id.desc())
                        .offset(offset)
                        .limit(limit)
                    )
                ).all()
            )

    @staticmethod
    def _search_pattern(search: str | None) -> str | None:
        if not search or not (normalized := search.strip()):
            return None
        escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    async def get_incident(self, tenant_id: UUID, incident_id: UUID) -> IncidentModel:
        async with tenant_session(tenant_id) as session:
            return await self._get(session, incident_id)

    async def create_incident(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        payload: IncidentCreate,
        correlation_id: UUID,
    ) -> IncidentModel:
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            incident = IncidentModel(
                tenant_id=tenant_id,
                code=f"INC-{uuid4().hex[:8].upper()}",
                title=payload.title,
                description=payload.description,
                severity=payload.severity,
                priority=payload.priority,
                classification=payload.classification,
                detected_at=now,
                is_simulated=False,
            )
            session.add(incident)
            await session.flush()
            self._timeline(session, incident, actor_id, "created", "Incident created", now)
            self._audit(
                session, tenant_id, actor_id, "incident.created", incident.id, correlation_id
            )
            return incident

    async def update_incident(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        incident_id: UUID,
        payload: IncidentUpdate,
        correlation_id: UUID,
    ) -> IncidentModel:
        async with tenant_session(tenant_id) as session:
            incident = await self._get(session, incident_id)
            self._expect_version(incident, payload.expected_version)
            for field in ("title", "description", "severity", "priority", "classification"):
                value = getattr(payload, field)
                if value is not None:
                    setattr(incident, field, value)
            incident.version += 1
            incident.updated_at = datetime.now(UTC)
            self._timeline(
                session,
                incident,
                actor_id,
                "updated",
                "Incident fields updated",
                incident.updated_at,
            )
            self._audit(
                session, tenant_id, actor_id, "incident.updated", incident.id, correlation_id
            )
            await session.flush()
            return incident

    async def transition(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        incident_id: UUID,
        payload: IncidentTransition,
        correlation_id: UUID,
    ) -> IncidentModel:
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            incident = await self._get(session, incident_id)
            self._expect_version(incident, payload.expected_version)
            if payload.target_status not in TRANSITIONS.get(incident.status, set()):
                raise InvalidTransition
            if payload.target_status in {"closed", "reopened"} and not payload.reason:
                raise InvalidTransition
            if payload.target_status == "closed" and payload.close_reason is None:
                raise InvalidTransition
            previous = incident.status
            incident.status = payload.target_status
            incident.version += 1
            incident.updated_at = now
            if payload.target_status == "triaged" and incident.acknowledged_at is None:
                incident.acknowledged_at = now
            if payload.target_status == "resolved":
                incident.resolved_at = now
            if payload.target_status == "closed":
                incident.closed_at = now
                incident.close_reason = payload.close_reason
                incident.close_comment = payload.reason
            if payload.target_status == "reopened":
                incident.closed_at = None
                incident.close_reason = None
                incident.close_comment = None
            self._timeline(
                session,
                incident,
                actor_id,
                "status_changed",
                f"{previous} -> {payload.target_status}: {payload.reason or 'workflow'}",
                now,
            )
            self._audit(
                session, tenant_id, actor_id, "incident.status.changed", incident.id, correlation_id
            )
            await session.flush()
            return incident

    async def assign(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        incident_id: UUID,
        payload: IncidentAssign,
        correlation_id: UUID,
    ) -> IncidentModel:
        async with tenant_session(tenant_id) as session:
            incident = await self._get(session, incident_id)
            self._expect_version(incident, payload.expected_version)
            if payload.assignee_user_id is not None:
                assignee = await session.get(UserModel, payload.assignee_user_id)
                if assignee is None or not assignee.is_active:
                    raise IncidentNotFound
            incident.assignee_user_id = payload.assignee_user_id
            incident.version += 1
            incident.updated_at = datetime.now(UTC)
            self._timeline(
                session,
                incident,
                actor_id,
                "assigned",
                f"Assignee set to {payload.assignee_user_id}",
                incident.updated_at,
            )
            self._audit(
                session, tenant_id, actor_id, "incident.assigned", incident.id, correlation_id
            )
            await session.flush()
            return incident

    async def list_timeline(
        self, tenant_id: UUID, incident_id: UUID
    ) -> list[IncidentTimelineModel]:
        async with tenant_session(tenant_id) as session:
            await self._get(session, incident_id)
            return list(
                (
                    await session.scalars(
                        select(IncidentTimelineModel)
                        .where(IncidentTimelineModel.incident_id == incident_id)
                        .order_by(IncidentTimelineModel.recorded_at)
                    )
                ).all()
            )

    async def add_timeline(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        incident_id: UUID,
        payload: TimelineCreate,
        correlation_id: UUID,
    ) -> IncidentTimelineModel:
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            incident = await self._get(session, incident_id)
            self._expect_version(incident, payload.expected_version)
            incident.version += 1
            incident.updated_at = now
            entry = self._timeline(session, incident, actor_id, "comment", payload.summary, now)
            self._audit(
                session, tenant_id, actor_id, "incident.timeline.added", incident.id, correlation_id
            )
            await session.flush()
            return entry

    @staticmethod
    async def _get(session: AsyncSession, incident_id: UUID) -> IncidentModel:
        incident = await session.scalar(
            select(IncidentModel).where(
                IncidentModel.id == incident_id,
                IncidentModel.is_simulated.is_(False),
            )
        )
        if incident is None:
            raise IncidentNotFound
        return incident

    @staticmethod
    def _expect_version(incident: IncidentModel, expected: int) -> None:
        if incident.version != expected:
            raise IncidentConflict

    @staticmethod
    def _timeline(
        session: AsyncSession,
        incident: IncidentModel,
        actor_id: UUID | None,
        entry_type: str,
        summary: str,
        effective_at: datetime,
    ) -> IncidentTimelineModel:
        entry = IncidentTimelineModel(
            tenant_id=incident.tenant_id,
            incident_id=incident.id,
            actor_user_id=actor_id,
            entry_type=entry_type,
            summary=summary,
            incident_version=incident.version,
            effective_at=effective_at,
        )
        session.add(entry)
        return entry

    @staticmethod
    def _audit(
        session: AsyncSession,
        tenant_id: UUID,
        actor_id: UUID,
        action: str,
        resource_id: UUID,
        correlation_id: UUID,
    ) -> None:
        session.add(
            AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                action=action,
                resource_type="incident",
                resource_id=resource_id,
                outcome="success",
                correlation_id=correlation_id,
                details={},
            )
        )
