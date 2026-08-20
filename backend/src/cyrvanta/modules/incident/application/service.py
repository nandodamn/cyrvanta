from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import case, delete, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.identity.infrastructure.models import (
    AuditEventModel,
    RoleModel,
    UserModel,
    UserRoleModel,
)
from cyrvanta.modules.incident.application.schemas import (
    AlertResponse,
    AlertTriageUpdate,
    CollaboratorAdd,
    CollaboratorResponse,
    HistoryEntry,
    IncidentAlertsLink,
    IncidentAssign,
    IncidentCreate,
    IncidentTransition,
    IncidentUpdate,
    Severity,
    TimelineCreate,
)
from cyrvanta.modules.incident.domain.authorization import (
    Actor,
    Denial,
    IncidentAction,
    IncidentFacts,
    allowed_actions,
    can,
)
from cyrvanta.modules.incident.infrastructure.models import (
    AlertReferenceModel,
    IncidentAlertModel,
    IncidentCollaboratorModel,
    IncidentModel,
    IncidentTimelineModel,
)
from cyrvanta.shared.database import tenant_session


class IncidentNotFound(Exception):
    pass


class ActionNotAllowed(Exception):
    """Refused by a contextual rule rather than by a missing permission.

    Carries the reason so the caller can say which one it was: "you own this
    case" and "you lack the permission" send someone to different places.
    """

    def __init__(self, reason: Denial) -> None:
        super().__init__(reason.value)
        self.reason = reason


class CollaboratorNotFound(Exception):
    """Named someone this tenant does not have, or an inactive account."""


class AlertNotFound(Exception):
    """An alert was named that this tenant does not have, or that is simulated.

    Raised for the whole request rather than skipping the unknown ids: an
    analyst attaching five alerts and getting three attached, silently, would
    believe the evidence is there when it is not.
    """


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

    async def link_alerts(
        self,
        tenant_id: UUID,
        incident_id: UUID,
        actor_id: UUID,
        payload: IncidentAlertsLink,
        correlation_id: UUID,
    ) -> list[AlertResponse]:
        """Attach alerts to an incident as evidence.

        Until this existed, only correlation and the entity-risk sweep could
        link an alert to an incident, so an incident opened by an analyst --
        the kind reported by a phone call, a CERT notice or an audit finding --
        could never hold any evidence at all. It could carry notes and change
        status, but nothing tying it to what was observed.

        Attaching is additive and there is no detach. Evidence an analyst
        connected to a case is part of that case's record; a mistake is
        corrected by saying so in the timeline, not by making it disappear.
        """
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            incident = await self._get(session, incident_id)
            self._expect_version(incident, payload.expected_version)

            requested = list(dict.fromkeys(payload.alert_ids))
            # Simulated alerts are excluded here as everywhere else: a demo
            # record must never become the evidence behind a real incident.
            found = list(
                (
                    await session.scalars(
                        select(AlertReferenceModel.id).where(
                            AlertReferenceModel.tenant_id == tenant_id,
                            AlertReferenceModel.id.in_(requested),
                            AlertReferenceModel.is_simulated.is_(False),
                        )
                    )
                ).all()
            )
            if len(found) != len(requested):
                raise AlertNotFound

            for alert_id in found:
                await session.execute(
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
            incident.version += 1
            incident.updated_at = now
            self._timeline(
                session,
                incident,
                actor_id,
                "evidence_linked",
                f"{len(found)} alert(s) attached as evidence",
                now,
            )
            self._audit(
                session,
                tenant_id,
                actor_id,
                "incident.evidence.linked",
                incident_id,
                correlation_id,
            )
            await session.flush()

        return await self.list_incident_alerts(tenant_id, incident_id)

    async def available_actions(
        self,
        tenant_id: UUID,
        incident_id: UUID,
        actor_id: UUID,
        permissions: frozenset[str],
    ) -> list[str]:
        """What this person can do to this incident, decided server-side.

        The interface asks rather than working it out, so there is one set of
        rules instead of two that can drift apart -- and so an action is never
        offered and then refused.
        """
        async with tenant_session(tenant_id) as session:
            incident = await self._get(session, incident_id)
            facts = await self._facts(session, incident)
        actor = Actor(user_id=actor_id, permissions=permissions)
        return [action.value for action in allowed_actions(actor, facts)]

    async def history(self, tenant_id: UUID, incident_id: UUID) -> list[HistoryEntry]:
        """The incident's record, in the order it happened.

        Two sources, one story. Audit events carry the structured change --
        what moved, from what, to what, and why -- while timeline entries carry
        what a person wrote in their own words. Reading only one of them leaves
        an auditor reconstructing the case from half of it.
        """
        async with tenant_session(tenant_id) as session:
            await self._get(session, incident_id)

            audits = (
                await session.execute(
                    select(AuditEventModel, UserModel.email, UserModel.display_name)
                    .outerjoin(UserModel, UserModel.id == AuditEventModel.actor_user_id)
                    .where(
                        AuditEventModel.tenant_id == tenant_id,
                        AuditEventModel.resource_id == incident_id,
                    )
                )
            ).all()
            entries = (
                await session.execute(
                    select(IncidentTimelineModel, UserModel.email, UserModel.display_name)
                    .outerjoin(UserModel, UserModel.id == IncidentTimelineModel.actor_user_id)
                    .where(IncidentTimelineModel.incident_id == incident_id)
                )
            ).all()

        history: list[HistoryEntry] = []
        for audit, email, name in audits:
            details = audit.details or {}
            history.append(
                HistoryEntry(
                    occurred_at=audit.occurred_at,
                    actor_email=email,
                    actor_name=name,
                    actor_roles=[str(role) for role in details.get("actor_roles", []) or []],
                    actor_relation=(
                        str(details["actor_relation"]) if details.get("actor_relation") else None
                    ),
                    action=audit.action,
                    before={k: str(v) for k, v in (details.get("before") or {}).items()},
                    after={k: str(v) for k, v in (details.get("after") or {}).items()},
                    reason=(str(details["reason"]) if details.get("reason") else None),
                    source="audit",
                )
            )
        for entry, email, name in entries:
            history.append(
                HistoryEntry(
                    occurred_at=entry.effective_at,
                    actor_email=email,
                    actor_name=name,
                    # An automatic entry has no actor: correlation and the risk
                    # sweep write here too, and attributing them to a person
                    # would be a lie in the one record meant to be trusted.
                    action=entry.entry_type,
                    reason=entry.summary,
                    source="timeline",
                )
            )
        # Newest first, and stable: two events in the same millisecond must not
        # swap places between reads of the same record.
        history.sort(key=lambda item: (item.occurred_at, item.source, item.action), reverse=True)
        return history

    async def list_collaborators(
        self, tenant_id: UUID, incident_id: UUID
    ) -> list[CollaboratorResponse]:
        async with tenant_session(tenant_id) as session:
            await self._get(session, incident_id)
            rows = (
                await session.execute(
                    select(IncidentCollaboratorModel, UserModel.email, UserModel.display_name)
                    .join(UserModel, UserModel.id == IncidentCollaboratorModel.user_id)
                    .where(IncidentCollaboratorModel.incident_id == incident_id)
                    .order_by(UserModel.display_name)
                )
            ).all()
        return [
            CollaboratorResponse(
                user_id=row.user_id,
                email=email,
                display_name=name,
                reason=row.reason,
                added_at=row.created_at,
            )
            for row, email, name in rows
        ]

    async def add_collaborator(
        self,
        tenant_id: UUID,
        incident_id: UUID,
        actor_id: UUID,
        payload: CollaboratorAdd,
        correlation_id: UUID,
    ) -> list[CollaboratorResponse]:
        """Bring someone in to help, without moving accountability.

        The owner stays the owner. A collaborator can contribute to the case --
        notes, evidence, work -- but not decide it is finished, which is why
        adding one is a change to the record rather than a private arrangement.
        """
        async with tenant_session(tenant_id) as session:
            incident = await self._get(session, incident_id)
            invitee = await session.scalar(
                select(UserModel).where(
                    UserModel.tenant_id == tenant_id,
                    UserModel.id == payload.user_id,
                    UserModel.is_active.is_(True),
                )
            )
            if invitee is None:
                raise CollaboratorNotFound
            actor_context = await self._actor_context(session, actor_id, incident)
            await session.execute(
                pg_insert(IncidentCollaboratorModel)
                .values(
                    tenant_id=tenant_id,
                    incident_id=incident_id,
                    user_id=payload.user_id,
                    added_by_user_id=actor_id,
                    reason=payload.reason,
                )
                .on_conflict_do_nothing(
                    index_elements=(
                        IncidentCollaboratorModel.tenant_id,
                        IncidentCollaboratorModel.incident_id,
                        IncidentCollaboratorModel.user_id,
                    )
                )
            )
            self._timeline(
                session,
                incident,
                actor_id,
                "collaborator_added",
                f"{invitee.display_name} joined as a collaborator",
                datetime.now(UTC),
            )
            self._audit(
                session,
                tenant_id,
                actor_id,
                "incident.collaborator.added",
                incident_id,
                correlation_id,
                {
                    "after": {"collaborator": invitee.email},
                    "reason": payload.reason,
                    **actor_context,
                },
            )
            await session.flush()
        return await self.list_collaborators(tenant_id, incident_id)

    async def remove_collaborator(
        self,
        tenant_id: UUID,
        incident_id: UUID,
        actor_id: UUID,
        user_id: UUID,
        correlation_id: UUID,
    ) -> list[CollaboratorResponse]:
        """Removing someone is audited as deliberately as adding them: who was
        allowed near a case, and until when, is part of its record.
        """
        async with tenant_session(tenant_id) as session:
            incident = await self._get(session, incident_id)
            removed = await session.scalar(select(UserModel).where(UserModel.id == user_id))
            actor_context = await self._actor_context(session, actor_id, incident)
            await session.execute(
                delete(IncidentCollaboratorModel).where(
                    IncidentCollaboratorModel.incident_id == incident_id,
                    IncidentCollaboratorModel.user_id == user_id,
                )
            )
            self._timeline(
                session,
                incident,
                actor_id,
                "collaborator_removed",
                f"{removed.display_name if removed else user_id} left the case",
                datetime.now(UTC),
            )
            self._audit(
                session,
                tenant_id,
                actor_id,
                "incident.collaborator.removed",
                incident_id,
                correlation_id,
                {
                    "before": {"collaborator": removed.email if removed else str(user_id)},
                    **actor_context,
                },
            )
            await session.flush()
        return await self.list_collaborators(tenant_id, incident_id)

    @staticmethod
    async def _facts(session: AsyncSession, incident: IncidentModel) -> IncidentFacts:
        """Everything the rules weigh, gathered once.

        The collaborator set is part of it: helping with a case and deciding it
        is finished are different things, and the rules cannot tell them apart
        without knowing who is helping.
        """
        collaborators = await session.scalars(
            select(IncidentCollaboratorModel.user_id).where(
                IncidentCollaboratorModel.incident_id == incident.id
            )
        )
        return IncidentFacts(
            status=incident.status,
            assignee_user_id=incident.assignee_user_id,
            resolved_by_user_id=incident.resolved_by_user_id,
            collaborator_ids=frozenset(collaborators.all()),
        )

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
        permissions: frozenset[str] = frozenset(),
    ) -> IncidentModel:
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            incident = await self._get(session, incident_id)
            self._expect_version(incident, payload.expected_version)
            # The permission was already checked by the router; this is the
            # part configuration cannot loosen -- whether this person may make
            # this move on this incident.
            decision = can(
                Actor(user_id=actor_id, permissions=permissions),
                IncidentFacts(status=incident.status, assignee_user_id=incident.assignee_user_id),
                IncidentAction(f"transition:{payload.target_status}"),
            )
            if not decision.allowed:
                if decision.reason is Denial.INVALID_TRANSITION:
                    raise InvalidTransition
                raise ActionNotAllowed(decision.reason or Denial.MISSING_PERMISSION)
            if payload.target_status not in TRANSITIONS.get(incident.status, set()):
                raise InvalidTransition
            if payload.target_status in {"closed", "reopened"} and not payload.reason:
                raise InvalidTransition
            if payload.target_status == "closed" and payload.close_reason is None:
                raise InvalidTransition
            actor_context = await self._actor_context(session, actor_id, incident)
            previous = incident.status
            incident.status = payload.target_status
            incident.version += 1
            incident.updated_at = now
            if payload.target_status == "triaged" and incident.acknowledged_at is None:
                incident.acknowledged_at = now
            if payload.target_status == "resolved":
                incident.resolved_at = now
                # Whose work a reviewer is being asked to accept, and what
                # stops that reviewer being the same person.
                incident.resolved_by_user_id = actor_id
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
                session,
                tenant_id,
                actor_id,
                "incident.status.changed",
                incident.id,
                correlation_id,
                {
                    "before": {"status": previous},
                    "after": {"status": payload.target_status},
                    "reason": payload.reason,
                    "close_reason": payload.close_reason,
                    # Reopening a resolved incident is a supervisor refusing
                    # the resolution, which is a different act from reopening
                    # a closed case months later. The record distinguishes
                    # them; the state machine cannot.
                    "resolution_rejected": (
                        previous == "resolved" and payload.target_status == "reopened"
                    ),
                    **actor_context,
                },
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
            previous_assignee = incident.assignee_user_id
            actor_context = await self._actor_context(session, actor_id, incident)
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
                session,
                tenant_id,
                actor_id,
                "incident.assigned",
                incident.id,
                correlation_id,
                {
                    "before": {"assignee_user_id": str(previous_assignee or "")},
                    "after": {"assignee_user_id": str(payload.assignee_user_id or "")},
                    **actor_context,
                },
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
        details: dict[str, object] | None = None,
    ) -> None:
        """Record what changed, not only that something did.

        Every one of these wrote an empty `details`, so the trail could say a
        status had been changed but not from what, to what, or why. Answering
        "who did what, when, from which state, to which, and for what reason"
        was impossible from the audit alone -- it had to be inferred from a
        sentence in the timeline, which is prose and cannot be relied on.
        """
        session.add(
            AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                action=action,
                resource_type="incident",
                resource_id=resource_id,
                outcome="success",
                correlation_id=correlation_id,
                details=details or {},
            )
        )

    @staticmethod
    async def _actor_context(
        session: AsyncSession, actor_id: UUID, incident: IncidentModel
    ) -> dict[str, object]:
        """What this person was to this incident at this moment.

        Stored rather than derived when the history is read. Roles change and
        assignments move, so working it out later would answer with today's
        arrangement and quietly rewrite what happened.
        """
        roles = await session.scalars(
            select(RoleModel.code)
            .join(UserRoleModel, UserRoleModel.role_id == RoleModel.id)
            .where(UserRoleModel.user_id == actor_id)
            .order_by(RoleModel.code)
        )
        return {
            "actor_roles": list(roles.all()),
            "actor_relation": ("owner" if incident.assignee_user_id == actor_id else "not_owner"),
        }
