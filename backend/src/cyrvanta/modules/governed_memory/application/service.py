import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.claims.infrastructure.models import ClaimModel
from cyrvanta.modules.decision.infrastructure.models import ActionProposalModel
from cyrvanta.modules.governed_memory.application.schemas import (
    FeedbackCreate,
    FeedbackList,
    FeedbackResponse,
    MemoryCandidateCreate,
    MemoryCandidateList,
    MemoryCandidateResponse,
    MemoryContextEvaluate,
    MemoryContextResponse,
    MemoryMatchResponse,
    MemoryMetricList,
    MemoryMetricResponse,
    MemoryReason,
    MemoryReviewCreate,
    MemoryReviewResponse,
    MemoryStateResponse,
)
from cyrvanta.modules.governed_memory.domain.models import (
    MemoryKind,
    MemoryStatus,
    assert_transition,
    review_target,
)
from cyrvanta.modules.governed_memory.infrastructure.models import (
    FeedbackEntryModel,
    MemoryCandidateModel,
    MemoryCandidateVersionModel,
    MemoryInfluenceModel,
    MemoryMetricDefinitionModel,
    MemoryMetricSnapshotModel,
    MemoryReviewModel,
    MemoryStateEventModel,
)
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
from cyrvanta.modules.incident.infrastructure.models import (
    AlertReferenceModel,
    IncidentModel,
)
from cyrvanta.modules.integrations.infrastructure.models import FindingRevisionModel
from cyrvanta.modules.playbooks.infrastructure.models import PlaybookExecutionModel
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.database import SessionFactory, tenant_session
from cyrvanta.shared.domain.events import DomainEvent
from cyrvanta.shared.infrastructure.event_store import SqlEventStore


class GovernedMemoryNotFound(Exception):
    pass


class GovernedMemoryConflict(Exception):
    pass


class GovernedMemoryService:
    async def create_feedback(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        payload: FeedbackCreate,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> FeedbackResponse:
        async with tenant_session(tenant_id) as session:
            existing = await session.scalar(
                select(FeedbackEntryModel).where(
                    FeedbackEntryModel.idempotency_key == idempotency_key
                )
            )
            if existing:
                if (
                    existing.resource_type != payload.resource_type
                    or existing.resource_id != payload.resource_id
                    or existing.outcome != payload.outcome.value
                    or existing.reason != payload.reason
                    or existing.is_synthetic != payload.is_synthetic
                ):
                    raise GovernedMemoryConflict("Idempotency key belongs to different feedback")
                return self._feedback_response(existing)
            source_synthetic = await self._source_synthetic(
                session, payload.resource_type, payload.resource_id
            )
            if source_synthetic is None:
                raise GovernedMemoryNotFound("Source resource was not found")
            entry = FeedbackEntryModel(
                tenant_id=tenant_id,
                resource_type=payload.resource_type,
                resource_id=payload.resource_id,
                actor_user_id=actor_user_id,
                outcome=payload.outcome.value,
                reason=payload.reason,
                is_synthetic=payload.is_synthetic or source_synthetic,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                occurred_at=payload.occurred_at,
            )
            session.add(entry)
            await session.flush()
            await self._record(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "feedback.recorded",
                "feedback",
                entry.id,
                {
                    "resource_type": entry.resource_type,
                    "outcome": entry.outcome,
                    "synthetic": entry.is_synthetic,
                },
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                "security.feedback.recorded",
                entry.id,
                {
                    "feedback_id": str(entry.id),
                    "resource_type": entry.resource_type,
                    "resource_id": str(entry.resource_id),
                    "outcome": entry.outcome,
                    "is_synthetic": entry.is_synthetic,
                },
            )
            return self._feedback_response(entry)

    async def list_feedback(
        self,
        tenant_id: UUID,
        *,
        resource_type: str | None,
        resource_id: UUID | None,
        limit: int,
        offset: int,
    ) -> FeedbackList:
        async with tenant_session(tenant_id) as session:
            query = select(FeedbackEntryModel)
            count = select(func.count(FeedbackEntryModel.id))
            if resource_type:
                query = query.where(FeedbackEntryModel.resource_type == resource_type)
                count = count.where(FeedbackEntryModel.resource_type == resource_type)
            if resource_id:
                query = query.where(FeedbackEntryModel.resource_id == resource_id)
                count = count.where(FeedbackEntryModel.resource_id == resource_id)
            items = list(
                (
                    await session.scalars(
                        query.order_by(FeedbackEntryModel.created_at.desc())
                        .limit(limit)
                        .offset(offset)
                    )
                ).all()
            )
            return FeedbackList(
                items=[self._feedback_response(item) for item in items],
                total=int(await session.scalar(count) or 0),
            )

    async def create_candidate(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        payload: MemoryCandidateCreate,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> MemoryCandidateResponse:
        settings = get_settings()
        if payload.valid_until - payload.valid_from > timedelta(
            days=settings.memory_max_validity_days
        ):
            raise GovernedMemoryConflict("Memory validity exceeds configured maximum")
        if (
            len(payload.conditions) > 20
            or len(json.dumps(payload.conditions, ensure_ascii=False)) > 16_384
        ):
            raise GovernedMemoryConflict("Memory conditions exceed safe limits")
        async with tenant_session(tenant_id) as session:
            existing = await session.scalar(
                select(MemoryCandidateModel).where(
                    MemoryCandidateModel.idempotency_key == idempotency_key
                )
            )
            if existing:
                existing_response = await self._candidate_response(session, existing)
                if (
                    existing.kind != payload.kind.value
                    or existing.source_type != payload.source_type.value
                    or existing_response.title_es != payload.title_es
                    or existing_response.title_en != payload.title_en
                    or existing_response.statement_es != payload.statement_es
                    or existing_response.statement_en != payload.statement_en
                ):
                    raise GovernedMemoryConflict(
                        "Idempotency key belongs to different memory candidate"
                    )
                return existing_response
            evidence = list(
                (
                    await session.scalars(
                        select(FeedbackEntryModel).where(
                            FeedbackEntryModel.id.in_(payload.evidence_refs)
                        )
                    )
                ).all()
            )
            if len({item.id for item in evidence}) != len(set(payload.evidence_refs)):
                raise GovernedMemoryNotFound("Evidence was not found")
            if payload.kind is MemoryKind.TREND:
                real_count = len({item.id for item in evidence if not item.is_synthetic})
                if real_count < settings.memory_minimum_sample_size:
                    raise GovernedMemoryConflict(
                        "Trend requires the configured minimum of real feedback entries"
                    )
            candidate = MemoryCandidateModel(
                tenant_id=tenant_id,
                kind=payload.kind.value,
                source_type=payload.source_type.value,
                created_by_user_id=actor_user_id,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            session.add(candidate)
            await session.flush()
            version = MemoryCandidateVersionModel(
                tenant_id=tenant_id,
                candidate_id=candidate.id,
                version=1,
                title_es=payload.title_es,
                title_en=payload.title_en,
                statement_es=payload.statement_es,
                statement_en=payload.statement_en,
                conditions=payload.conditions,
                evidence_refs=[str(item) for item in payload.evidence_refs],
                is_synthetic=payload.is_synthetic or any(item.is_synthetic for item in evidence),
                valid_from=payload.valid_from,
                valid_until=payload.valid_until,
            )
            session.add(version)
            await session.flush()
            await self._state(
                session,
                tenant_id,
                version.id,
                actor_user_id,
                None,
                MemoryStatus.DRAFT,
                "candidate_created",
                correlation_id,
            )
            await self._record(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "memory.candidate.proposed",
                "memory_candidate",
                candidate.id,
                {
                    "version_id": str(version.id),
                    "kind": candidate.kind,
                    "source_type": candidate.source_type,
                },
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                "security.memory_candidate.proposed",
                candidate.id,
                {
                    "candidate_id": str(candidate.id),
                    "version_id": str(version.id),
                    "kind": candidate.kind,
                    "source_type": candidate.source_type,
                },
            )
            return await self._candidate_response(session, candidate)

    async def list_candidates(
        self, tenant_id: UUID, *, limit: int, offset: int
    ) -> MemoryCandidateList:
        async with tenant_session(tenant_id) as session:
            candidates = list(
                (
                    await session.scalars(
                        select(MemoryCandidateModel)
                        .order_by(MemoryCandidateModel.created_at.desc())
                        .limit(limit)
                        .offset(offset)
                    )
                ).all()
            )
            total = int(await session.scalar(select(func.count(MemoryCandidateModel.id))) or 0)
            return MemoryCandidateList(
                items=[await self._candidate_response(session, item) for item in candidates],
                total=total,
            )

    async def get_candidate(self, tenant_id: UUID, candidate_id: UUID) -> MemoryCandidateResponse:
        async with tenant_session(tenant_id) as session:
            candidate = await session.scalar(
                select(MemoryCandidateModel).where(MemoryCandidateModel.id == candidate_id)
            )
            if candidate is None:
                raise GovernedMemoryNotFound("Memory candidate was not found")
            return await self._candidate_response(session, candidate)

    async def request_review(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        version_id: UUID,
        payload: MemoryReason,
        correlation_id: UUID,
    ) -> MemoryCandidateResponse:
        return await self._transition(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            version_id=version_id,
            expected=MemoryStatus.DRAFT,
            target=MemoryStatus.IN_REVIEW,
            reason=payload.reason,
            correlation_id=correlation_id,
            event_name="security.memory_candidate.review_requested",
            audit_action="memory.review.requested",
        )

    async def review(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        version_id: UUID,
        payload: MemoryReviewCreate,
        correlation_id: UUID,
    ) -> MemoryCandidateResponse:
        async with tenant_session(tenant_id) as session:
            version, candidate = await self._version_candidate(session, version_id)
            current = await self._current_status(session, version.id)
            if current is not MemoryStatus.IN_REVIEW:
                raise GovernedMemoryConflict("Memory version is not in review")
            if candidate.created_by_user_id == actor_user_id:
                raise GovernedMemoryConflict("Memory author cannot review own version")
            existing = await session.scalar(
                select(MemoryReviewModel).where(
                    MemoryReviewModel.version_id == version.id,
                    MemoryReviewModel.reviewer_user_id == actor_user_id,
                )
            )
            if existing:
                if existing.decision != payload.decision.value:
                    raise GovernedMemoryConflict("Reviewer already submitted a different decision")
                return await self._candidate_response(session, candidate)
            review = MemoryReviewModel(
                tenant_id=tenant_id,
                version_id=version.id,
                reviewer_user_id=actor_user_id,
                decision=payload.decision.value,
                reason=payload.reason.strip(),
            )
            session.add(review)
            await session.flush()
            target = review_target(payload.decision)
            assert_transition(current, target)
            await self._state(
                session,
                tenant_id,
                version.id,
                actor_user_id,
                current,
                target,
                payload.reason,
                correlation_id,
            )
            await self._record(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "memory.candidate.reviewed",
                "memory_version",
                version.id,
                {"review_id": str(review.id), "decision": review.decision},
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                "security.memory_candidate.reviewed",
                version.id,
                {
                    "version_id": str(version.id),
                    "review_id": str(review.id),
                    "decision": review.decision,
                },
            )
            return await self._candidate_response(session, candidate)

    async def activate(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        version_id: UUID,
        payload: MemoryReason,
        correlation_id: UUID,
    ) -> MemoryCandidateResponse:
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            version, candidate = await self._version_candidate(session, version_id)
            current = await self._current_status(session, version.id)
            if current is MemoryStatus.ACTIVE:
                return await self._candidate_response(session, candidate)
            if current is not MemoryStatus.APPROVED:
                raise GovernedMemoryConflict("Memory version is not approved")
            if actor_user_id == candidate.created_by_user_id:
                raise GovernedMemoryConflict("Memory author cannot activate own version")
            if version.is_synthetic or version.valid_until <= now:
                raise GovernedMemoryConflict("Synthetic or expired memory cannot be activated")
            assert_transition(current, MemoryStatus.ACTIVE)
            await self._state(
                session,
                tenant_id,
                version.id,
                actor_user_id,
                current,
                MemoryStatus.ACTIVE,
                payload.reason,
                correlation_id,
            )
            await self._record(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "memory.version.activated",
                "memory_version",
                version.id,
                {
                    "valid_from": version.valid_from.isoformat(),
                    "valid_until": version.valid_until.isoformat(),
                },
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                "security.memory_version.activated",
                version.id,
                {
                    "version_id": str(version.id),
                    "valid_from": version.valid_from.isoformat(),
                    "valid_until": version.valid_until.isoformat(),
                },
            )
            return await self._candidate_response(session, candidate)

    async def disable(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        version_id: UUID,
        payload: MemoryReason,
        correlation_id: UUID,
    ) -> MemoryCandidateResponse:
        async with tenant_session(tenant_id) as session:
            version, candidate = await self._version_candidate(session, version_id)
            current = await self._current_status(session, version.id)
            if current is MemoryStatus.DISABLED:
                return await self._candidate_response(session, candidate)
            if current not in {MemoryStatus.APPROVED, MemoryStatus.ACTIVE}:
                raise GovernedMemoryConflict("Memory version cannot be disabled")
            assert_transition(current, MemoryStatus.DISABLED)
            await self._state(
                session,
                tenant_id,
                version.id,
                actor_user_id,
                current,
                MemoryStatus.DISABLED,
                payload.reason,
                correlation_id,
            )
            await self._record(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "memory.version.disabled",
                "memory_version",
                version.id,
                {"reason_code": "MANUAL_DISABLE"},
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                "security.memory_version.disabled",
                version.id,
                {"version_id": str(version.id), "reason_code": "MANUAL_DISABLE"},
            )
            return await self._candidate_response(session, candidate)

    async def list_active(self, tenant_id: UUID, *, limit: int, offset: int) -> MemoryCandidateList:
        now = datetime.now(UTC)
        async with tenant_session(tenant_id) as session:
            version_ids = select(MemoryStateEventModel.version_id).where(
                MemoryStateEventModel.to_status == MemoryStatus.ACTIVE.value
            )
            versions = list(
                (
                    await session.scalars(
                        select(MemoryCandidateVersionModel)
                        .where(
                            MemoryCandidateVersionModel.id.in_(version_ids),
                            MemoryCandidateVersionModel.valid_from <= now,
                            MemoryCandidateVersionModel.valid_until > now,
                            MemoryCandidateVersionModel.is_synthetic.is_(False),
                        )
                        .order_by(MemoryCandidateVersionModel.valid_until)
                        .limit(limit)
                        .offset(offset)
                    )
                ).all()
            )
            active = []
            for version in versions:
                if await self._current_status(session, version.id) is MemoryStatus.ACTIVE:
                    candidate = await session.scalar(
                        select(MemoryCandidateModel).where(
                            MemoryCandidateModel.id == version.candidate_id
                        )
                    )
                    if candidate:
                        active.append(await self._candidate_response(session, candidate))
            return MemoryCandidateList(items=active, total=len(active))

    async def evaluate_context(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        payload: MemoryContextEvaluate,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> MemoryContextResponse:
        settings = get_settings()
        if not settings.memory_influence_enabled:
            async with tenant_session(tenant_id) as session:
                await self._record(
                    session,
                    tenant_id,
                    actor_user_id,
                    correlation_id,
                    "memory.influence.omitted",
                    "memory_consumer",
                    payload.consumer_id,
                    {
                        "consumer_type": payload.consumer_type,
                        "reason_code": "INFLUENCE_DISABLED",
                        "base_fingerprint": payload.base_fingerprint,
                    },
                )
            return MemoryContextResponse(
                influence_enabled=False,
                base_fingerprint=payload.base_fingerprint,
                presented_fingerprint=payload.base_fingerprint,
                matches=[],
            )
        active = await self.list_active(tenant_id, limit=100, offset=0)
        matched_items = [
            item
            for item in active.items
            if all(payload.context.get(key) == value for key, value in item.conditions.items())
        ]
        material = {
            "base": payload.base_fingerprint,
            "versions": sorted(str(item.version_id) for item in matched_items),
        }
        presented = hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        matches: list[MemoryMatchResponse] = []
        async with tenant_session(tenant_id) as session:
            for index, item in enumerate(matched_items):
                explanation = f"OBSERVATIONAL_ONLY:{item.version_id}:v{item.version}"
                influence = MemoryInfluenceModel(
                    tenant_id=tenant_id,
                    version_id=item.version_id,
                    consumer_type=payload.consumer_type,
                    consumer_id=payload.consumer_id,
                    matched=True,
                    base_fingerprint=payload.base_fingerprint,
                    presented_fingerprint=presented,
                    explanation=explanation,
                    idempotency_key=f"{idempotency_key}:{index}",
                    correlation_id=correlation_id,
                    occurred_at=datetime.now(UTC),
                )
                session.add(influence)
                await session.flush()
                await self._event(
                    session,
                    tenant_id,
                    correlation_id,
                    "security.memory.influence_recorded",
                    influence.id,
                    {
                        "version_id": str(item.version_id),
                        "consumer_type": payload.consumer_type,
                        "consumer_id": str(payload.consumer_id),
                        "matched": True,
                        "base_fingerprint": payload.base_fingerprint,
                        "presented_fingerprint": presented,
                    },
                )
                await self._record(
                    session,
                    tenant_id,
                    actor_user_id,
                    correlation_id,
                    "memory.influence.recorded",
                    "memory_influence",
                    influence.id,
                    {
                        "version_id": str(item.version_id),
                        "consumer_type": payload.consumer_type,
                        "matched": True,
                    },
                )
                matches.append(
                    MemoryMatchResponse(
                        version_id=item.version_id, matched=True, explanation=explanation
                    )
                )
        return MemoryContextResponse(
            influence_enabled=True,
            base_fingerprint=payload.base_fingerprint,
            presented_fingerprint=presented,
            matches=matches,
        )

    async def list_metrics(self, tenant_id: UUID, *, limit: int, offset: int) -> MemoryMetricList:
        async with tenant_session(tenant_id) as session:
            rows = (
                await session.execute(
                    select(MemoryMetricSnapshotModel, MemoryMetricDefinitionModel)
                    .join(
                        MemoryMetricDefinitionModel,
                        MemoryMetricDefinitionModel.id == MemoryMetricSnapshotModel.definition_id,
                    )
                    .order_by(MemoryMetricSnapshotModel.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            total = int(await session.scalar(select(func.count(MemoryMetricSnapshotModel.id))) or 0)
            return MemoryMetricList(
                items=[
                    MemoryMetricResponse(
                        id=s.id,
                        code=d.code,
                        version=d.version,
                        window_start=s.window_start,
                        window_end=s.window_end,
                        sample_size=s.sample_size,
                        numerator=s.numerator,
                        denominator=s.denominator,
                        value=s.value,
                        sufficient_sample=s.sufficient_sample,
                        input_fingerprint=s.input_fingerprint,
                    )
                    for s, d in rows
                ],
                total=total,
            )

    async def expire_due(self, batch_size: int = 100) -> int:
        async with SessionFactory() as discovery_session, discovery_session.begin():
            rows = (
                (
                    await discovery_session.execute(
                        text("SELECT * FROM public.list_due_memory_expirations(:batch_size)"),
                        {"batch_size": batch_size},
                    )
                )
                .mappings()
                .all()
            )
        expired = 0
        for row in rows:
            tenant_id = UUID(str(row["tenant_id"]))
            version_id = UUID(str(row["version_id"]))
            correlation_id = uuid4()
            async with tenant_session(tenant_id) as session:
                version = await session.scalar(
                    select(MemoryCandidateVersionModel)
                    .where(MemoryCandidateVersionModel.id == version_id)
                    .with_for_update()
                )
                if version is None or version.valid_until > datetime.now(UTC):
                    continue
                current = await self._current_status(session, version.id)
                if current is not MemoryStatus.ACTIVE:
                    continue
                assert_transition(current, MemoryStatus.EXPIRED)
                await self._state(
                    session,
                    tenant_id,
                    version.id,
                    None,
                    current,
                    MemoryStatus.EXPIRED,
                    "validity_window_elapsed",
                    correlation_id,
                )
                await self._record(
                    session,
                    tenant_id,
                    None,
                    correlation_id,
                    "memory.version.expired",
                    "memory_version",
                    version.id,
                    {"expiration_instant": version.valid_until.isoformat()},
                )
                await self._event(
                    session,
                    tenant_id,
                    correlation_id,
                    "security.memory_version.expired",
                    version.id,
                    {
                        "version_id": str(version.id),
                        "expiration_instant": version.valid_until.isoformat(),
                    },
                )
                expired += 1
        return expired

    async def _transition(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        version_id: UUID,
        expected: MemoryStatus,
        target: MemoryStatus,
        reason: str,
        correlation_id: UUID,
        event_name: str,
        audit_action: str,
    ) -> MemoryCandidateResponse:
        async with tenant_session(tenant_id) as session:
            version, candidate = await self._version_candidate(session, version_id)
            current = await self._current_status(session, version.id)
            if current is target:
                return await self._candidate_response(session, candidate)
            if current is not expected:
                raise GovernedMemoryConflict(f"Memory version must be {expected.value}")
            assert_transition(current, target)
            await self._state(
                session,
                tenant_id,
                version.id,
                actor_user_id,
                current,
                target,
                reason,
                correlation_id,
            )
            await self._record(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                audit_action,
                "memory_version",
                version.id,
                {"from": current.value, "to": target.value},
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                event_name,
                version.id,
                {"candidate_id": str(candidate.id), "version_id": str(version.id)},
            )
            return await self._candidate_response(session, candidate)

    @staticmethod
    def _feedback_response(item: FeedbackEntryModel) -> FeedbackResponse:
        return FeedbackResponse(
            id=item.id,
            resource_type=item.resource_type,
            resource_id=item.resource_id,
            actor_user_id=item.actor_user_id,
            outcome=item.outcome,
            reason=item.reason,
            is_synthetic=item.is_synthetic,
            occurred_at=item.occurred_at,
            created_at=item.created_at,
        )

    async def _candidate_response(
        self, session: AsyncSession, candidate: MemoryCandidateModel
    ) -> MemoryCandidateResponse:
        version = await session.scalar(
            select(MemoryCandidateVersionModel)
            .where(MemoryCandidateVersionModel.candidate_id == candidate.id)
            .order_by(MemoryCandidateVersionModel.version.desc())
            .limit(1)
        )
        if version is None:
            raise RuntimeError("Memory candidate version is missing")
        reviews = list(
            (
                await session.scalars(
                    select(MemoryReviewModel)
                    .where(MemoryReviewModel.version_id == version.id)
                    .order_by(MemoryReviewModel.created_at)
                )
            ).all()
        )
        states = list(
            (
                await session.scalars(
                    select(MemoryStateEventModel)
                    .where(MemoryStateEventModel.version_id == version.id)
                    .order_by(MemoryStateEventModel.occurred_at, MemoryStateEventModel.id)
                )
            ).all()
        )
        if not states:
            raise RuntimeError("Memory state history is missing")
        return MemoryCandidateResponse(
            id=candidate.id,
            version_id=version.id,
            version=version.version,
            kind=candidate.kind,
            source_type=candidate.source_type,
            created_by_user_id=candidate.created_by_user_id,
            title_es=version.title_es,
            title_en=version.title_en,
            statement_es=version.statement_es,
            statement_en=version.statement_en,
            conditions=dict(version.conditions),
            evidence_refs=[UUID(item) for item in version.evidence_refs],
            is_synthetic=version.is_synthetic,
            valid_from=version.valid_from,
            valid_until=version.valid_until,
            status=states[-1].to_status,
            reviews=[
                MemoryReviewResponse(
                    id=r.id,
                    reviewer_user_id=r.reviewer_user_id,
                    decision=r.decision,
                    reason=r.reason,
                    created_at=r.created_at,
                )
                for r in reviews
            ],
            state_history=[
                MemoryStateResponse(
                    id=s.id,
                    actor_user_id=s.actor_user_id,
                    from_status=s.from_status,
                    to_status=s.to_status,
                    reason=s.reason,
                    occurred_at=s.occurred_at,
                )
                for s in states
            ],
            created_at=candidate.created_at,
        )

    async def _version_candidate(
        self, session: AsyncSession, version_id: UUID
    ) -> tuple[MemoryCandidateVersionModel, MemoryCandidateModel]:
        version = await session.scalar(
            select(MemoryCandidateVersionModel)
            .where(MemoryCandidateVersionModel.id == version_id)
            .with_for_update()
        )
        if version is None:
            raise GovernedMemoryNotFound("Memory version was not found")
        candidate = await session.scalar(
            select(MemoryCandidateModel).where(MemoryCandidateModel.id == version.candidate_id)
        )
        if candidate is None:
            raise GovernedMemoryNotFound("Memory candidate was not found")
        return version, candidate

    async def _current_status(self, session: AsyncSession, version_id: UUID) -> MemoryStatus:
        value = await session.scalar(
            select(MemoryStateEventModel.to_status)
            .where(MemoryStateEventModel.version_id == version_id)
            .order_by(MemoryStateEventModel.occurred_at.desc(), MemoryStateEventModel.id.desc())
            .limit(1)
        )
        if value is None:
            raise GovernedMemoryConflict("Memory state history is missing")
        return MemoryStatus(value)

    @staticmethod
    async def _state(
        session: AsyncSession,
        tenant_id: UUID,
        version_id: UUID,
        actor_user_id: UUID | None,
        current: MemoryStatus | None,
        target: MemoryStatus,
        reason: str,
        correlation_id: UUID,
    ) -> None:
        session.add(
            MemoryStateEventModel(
                tenant_id=tenant_id,
                version_id=version_id,
                actor_user_id=actor_user_id,
                from_status=current.value if current else None,
                to_status=target.value,
                reason=reason.strip(),
                occurred_at=datetime.now(UTC),
                correlation_id=correlation_id,
            )
        )
        await session.flush()

    @staticmethod
    async def _source_synthetic(
        session: AsyncSession, resource_type: str, resource_id: UUID
    ) -> bool | None:
        if resource_type == "INCIDENT":
            return cast(
                bool | None,
                await session.scalar(
                    select(IncidentModel.is_simulated).where(IncidentModel.id == resource_id)
                ),
            )
        if resource_type == "FINDING":
            return cast(
                bool | None,
                await session.scalar(
                    select(AlertReferenceModel.is_simulated)
                    .join(
                        FindingRevisionModel,
                        FindingRevisionModel.alert_reference_id == AlertReferenceModel.id,
                    )
                    .where(FindingRevisionModel.id == resource_id)
                ),
            )
        if resource_type == "CLAIM":
            return cast(
                bool | None,
                await session.scalar(
                    select(ClaimModel.is_simulated).where(ClaimModel.id == resource_id)
                ),
            )
        if resource_type == "ACTION_PROPOSAL":
            return cast(
                bool | None,
                await session.scalar(
                    select(ActionProposalModel.is_simulated).where(
                        ActionProposalModel.id == resource_id
                    )
                ),
            )
        if resource_type == "PLAYBOOK_EXECUTION":
            return cast(
                bool | None,
                await session.scalar(
                    select(IncidentModel.is_simulated)
                    .join(
                        PlaybookExecutionModel,
                        PlaybookExecutionModel.incident_id == IncidentModel.id,
                    )
                    .where(PlaybookExecutionModel.id == resource_id)
                ),
            )
        return None

    @staticmethod
    async def _record(
        session: AsyncSession,
        tenant_id: UUID,
        actor_user_id: UUID | None,
        correlation_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID,
        details: dict[str, object],
    ) -> None:
        session.add(
            AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="success",
                correlation_id=correlation_id,
                details=details,
            )
        )

    @staticmethod
    async def _event(
        session: AsyncSession,
        tenant_id: UUID,
        correlation_id: UUID,
        event_name: str,
        aggregate_id: UUID,
        payload: dict[str, object],
    ) -> None:
        store = SqlEventStore(SessionFactory, get_settings().event_max_payload_bytes)
        await store.recorder(session).add(
            DomainEvent.create(
                event_name=event_name,
                tenant_id=tenant_id,
                aggregate_type="governed_memory",
                aggregate_id=aggregate_id,
                correlation_id=correlation_id,
                producer="governed_memory",
                payload=payload,
            )
        )
