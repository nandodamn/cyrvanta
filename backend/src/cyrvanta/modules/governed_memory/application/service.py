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
    MemoryVersionCreate,
)
from cyrvanta.modules.governed_memory.domain.metrics import (
    DEFINITION_VERSION,
    DENOMINATOR,
    NUMERATOR,
    MetricCode,
    tally,
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
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, UserModel
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

# Thirty days: long enough for a small SOC to assess twenty cases, short
# enough that a number still describes how the team works now.
_METRIC_WINDOW_DAYS = 30


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
            if source_synthetic:
                raise GovernedMemoryConflict("Synthetic legacy sources are not operational")
            entry = FeedbackEntryModel(
                tenant_id=tenant_id,
                resource_type=payload.resource_type,
                resource_id=payload.resource_id,
                actor_user_id=actor_user_id,
                outcome=payload.outcome.value,
                reason=payload.reason,
                is_synthetic=False,
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
            query = select(FeedbackEntryModel).where(FeedbackEntryModel.is_synthetic.is_(False))
            count = select(func.count(FeedbackEntryModel.id)).where(
                FeedbackEntryModel.is_synthetic.is_(False)
            )
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
            labels = await self._resource_labels(session, items)
            authors = await self._author_names(session, {item.actor_user_id for item in items})
            return FeedbackList(
                items=[
                    self._feedback_response(
                        item,
                        resource_label=labels.get(item.resource_id),
                        actor_name=authors.get(item.actor_user_id),
                    )
                    for item in items
                ],
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
                            FeedbackEntryModel.id.in_(payload.evidence_refs),
                            FeedbackEntryModel.is_synthetic.is_(False),
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
                created_by_user_id=actor_user_id,
                title_es=payload.title_es,
                title_en=payload.title_en,
                statement_es=payload.statement_es,
                statement_en=payload.statement_en,
                conditions=payload.conditions,
                evidence_refs=[str(item) for item in payload.evidence_refs],
                is_synthetic=False,
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
                        .join(
                            MemoryCandidateVersionModel,
                            MemoryCandidateVersionModel.candidate_id == MemoryCandidateModel.id,
                        )
                        .where(MemoryCandidateVersionModel.is_synthetic.is_(False))
                        .distinct()
                        .order_by(MemoryCandidateModel.created_at.desc())
                        .limit(limit)
                        .offset(offset)
                    )
                ).all()
            )
            total = int(
                await session.scalar(
                    select(func.count(func.distinct(MemoryCandidateModel.id)))
                    .join(
                        MemoryCandidateVersionModel,
                        MemoryCandidateVersionModel.candidate_id == MemoryCandidateModel.id,
                    )
                    .where(MemoryCandidateVersionModel.is_synthetic.is_(False))
                )
                or 0
            )
            return MemoryCandidateList(
                items=[await self._candidate_response(session, item) for item in candidates],
                total=total,
            )

    async def get_candidate(self, tenant_id: UUID, candidate_id: UUID) -> MemoryCandidateResponse:
        async with tenant_session(tenant_id) as session:
            candidate = await session.scalar(
                select(MemoryCandidateModel)
                .join(
                    MemoryCandidateVersionModel,
                    MemoryCandidateVersionModel.candidate_id == MemoryCandidateModel.id,
                )
                .where(
                    MemoryCandidateModel.id == candidate_id,
                    MemoryCandidateVersionModel.is_synthetic.is_(False),
                )
            )
            if candidate is None:
                raise GovernedMemoryNotFound("Memory candidate was not found")
            return await self._candidate_response(session, candidate)

    async def create_version(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        candidate_id: UUID,
        payload: MemoryVersionCreate,
        correlation_id: UUID,
    ) -> MemoryCandidateResponse:
        """Correct a memory by writing a new version of it.

        Nothing is edited. The previous version keeps its text, its reviews and
        its state history exactly as they were, which is the whole reason this
        module stores versions at all -- an approved statement that can be
        rewritten in place is an approval of nothing.

        A correction to a memory that is currently live supersedes it in the
        same transaction. Leaving the old one active while its replacement
        waits for review would mean the incident screen keeps showing advice
        that somebody has already judged wrong.
        """
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
            candidate = await session.scalar(
                select(MemoryCandidateModel).where(MemoryCandidateModel.id == candidate_id)
            )
            if candidate is None:
                raise GovernedMemoryNotFound("Memory candidate was not found")
            previous = await session.scalar(
                select(MemoryCandidateVersionModel)
                .where(
                    MemoryCandidateVersionModel.candidate_id == candidate.id,
                    MemoryCandidateVersionModel.is_synthetic.is_(False),
                )
                .order_by(MemoryCandidateVersionModel.version.desc())
                .limit(1)
                .with_for_update()
            )
            if previous is None:
                raise GovernedMemoryNotFound("Memory candidate version was not found")
            previous_status = await self._current_status(session, previous.id)
            if previous_status in {MemoryStatus.IN_REVIEW, MemoryStatus.APPROVED}:
                # Mid-review, a correction would leave a reviewer judging text
                # that no longer exists. Approved-but-not-yet-active is the
                # same problem one step later: the approval on record would be
                # of a statement nobody can read any more.
                raise GovernedMemoryConflict(
                    "A version awaiting review or activation cannot be corrected"
                )

            evidence = list(
                (
                    await session.scalars(
                        select(FeedbackEntryModel).where(
                            FeedbackEntryModel.id.in_(payload.evidence_refs),
                            FeedbackEntryModel.is_synthetic.is_(False),
                        )
                    )
                ).all()
            )
            if len({item.id for item in evidence}) != len(set(payload.evidence_refs)):
                raise GovernedMemoryNotFound("Evidence was not found")
            if candidate.kind == MemoryKind.TREND.value:
                if len(evidence) < settings.memory_minimum_sample_size:
                    raise GovernedMemoryConflict(
                        "Trend requires the configured minimum of real feedback entries"
                    )

            version = MemoryCandidateVersionModel(
                tenant_id=tenant_id,
                candidate_id=candidate.id,
                version=previous.version + 1,
                created_by_user_id=actor_user_id,
                title_es=payload.title_es,
                title_en=payload.title_en,
                statement_es=payload.statement_es,
                statement_en=payload.statement_en,
                conditions=payload.conditions,
                evidence_refs=[str(item) for item in payload.evidence_refs],
                is_synthetic=False,
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
                payload.reason,
                correlation_id,
            )
            if previous_status is MemoryStatus.ACTIVE:
                assert_transition(previous_status, MemoryStatus.SUPERSEDED)
                await self._state(
                    session,
                    tenant_id,
                    previous.id,
                    actor_user_id,
                    previous_status,
                    MemoryStatus.SUPERSEDED,
                    f"superseded_by_v{version.version}",
                    correlation_id,
                )
                await self._event(
                    session,
                    tenant_id,
                    correlation_id,
                    "security.memory_version.superseded",
                    previous.id,
                    {
                        "version_id": str(previous.id),
                        "superseded_by_version_id": str(version.id),
                    },
                )
            await self._record(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "memory.version.corrected",
                "memory_version",
                version.id,
                {
                    "candidate_id": str(candidate.id),
                    "version": version.version,
                    "previous_version_id": str(previous.id),
                    "previous_status": previous_status.value,
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
            # Read off the version, not the candidate: a correction is written
            # by whoever corrects it, and they are the one who must not judge it.
            if version.created_by_user_id == actor_user_id:
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
            if actor_user_id == version.created_by_user_id:
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
                key = f"{idempotency_key}:{index}"
                matches.append(
                    MemoryMatchResponse(
                        version_id=item.version_id,
                        version=item.version,
                        title_es=item.title_es,
                        title_en=item.title_en,
                        statement_es=item.statement_es,
                        statement_en=item.statement_en,
                        valid_until=item.valid_until,
                        matched=True,
                        explanation=explanation,
                    )
                )
                # The same consultation, repeated, is still one consultation.
                # Opening an incident twice must not grow the influence ledger,
                # or it stops being a record of where memory was used.
                if await session.scalar(
                    select(func.count(MemoryInfluenceModel.id)).where(
                        MemoryInfluenceModel.idempotency_key == key
                    )
                ):
                    continue
                influence = MemoryInfluenceModel(
                    tenant_id=tenant_id,
                    version_id=item.version_id,
                    consumer_type=payload.consumer_type,
                    consumer_id=payload.consumer_id,
                    matched=True,
                    base_fingerprint=payload.base_fingerprint,
                    presented_fingerprint=presented,
                    explanation=explanation,
                    idempotency_key=key,
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
        return MemoryContextResponse(
            influence_enabled=True,
            base_fingerprint=payload.base_fingerprint,
            presented_fingerprint=presented,
            matches=matches,
        )

    async def incident_context(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        incident_id: UUID,
        correlation_id: UUID,
    ) -> MemoryContextResponse:
        """Which active memories apply to this incident.

        The context is built here rather than sent by the browser. A caller
        that chooses its own facts chooses its own matches, and the fingerprint
        is supposed to be evidence of what the incident actually was when the
        memory was shown -- not of what a client said it was.

        Observational only, and it says so: the matches are context a person
        reads, and nothing in this path writes to the incident.
        """
        async with tenant_session(tenant_id) as session:
            incident = await session.scalar(
                select(IncidentModel).where(IncidentModel.id == incident_id)
            )
            if incident is None:
                raise GovernedMemoryNotFound("Incident was not found")
            context: dict[str, object] = {
                "severity": incident.severity,
                "classification": incident.classification,
                "status": incident.status,
            }
            base = hashlib.sha256(
                json.dumps(
                    {"incident": str(incident_id), "context": context},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        return await self.evaluate_context(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            payload=MemoryContextEvaluate(
                consumer_type="INCIDENT_VIEW",
                consumer_id=incident_id,
                base_fingerprint=base,
                context=context,
            ),
            # Deterministic: opening the same incident twice is one consultation
            # of the same memory against the same facts, not two. Without this
            # the influence ledger would grow with every page view and stop
            # being readable as a record of where memory was actually used.
            idempotency_key=f"incident-view:{incident_id}:{base[:16]}",
            correlation_id=correlation_id,
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

    async def compute_metrics(self) -> int:
        """Take one reproducible reading of the feedback ledger per tenant.

        Snapshots rather than a query behind the screen: a metric read live
        changes under the reader, so two people looking at the same number on
        the same day can see different things and neither can say which was
        right. A snapshot carries its window, its counts, its definition
        version and a fingerprint of its inputs, so it can be recomputed and
        disputed later.

        Written once per definition per day. Re-running the scheduler minutes
        later must not fill the table with near-identical rows.
        """
        async with SessionFactory() as discovery_session:
            tenant_ids = [
                UUID(str(row[0]))
                for row in (await discovery_session.execute(text("SELECT id FROM tenants"))).all()
            ]
        written = 0
        now = datetime.now(UTC)
        for tenant_id in tenant_ids:
            async with tenant_session(tenant_id) as session:
                for code in MetricCode:
                    definition = await self._metric_definition(session, tenant_id, code)
                    window_start = now - timedelta(days=definition.window_days)
                    outcomes = list(
                        (
                            await session.scalars(
                                select(FeedbackEntryModel.outcome).where(
                                    FeedbackEntryModel.is_synthetic.is_(False),
                                    FeedbackEntryModel.occurred_at >= window_start,
                                    FeedbackEntryModel.occurred_at <= now,
                                )
                            )
                        ).all()
                    )
                    ratio = tally(outcomes, code, definition.minimum_sample_size)
                    # A window nobody assessed has no population, and the
                    # schema refuses to store a ratio without one -- rightly:
                    # zero out of zero is not a rate, and writing it as 0%
                    # would put a confident-looking number on a month in which
                    # nothing was measured. The absence of a snapshot is the
                    # honest record of that.
                    if ratio.denominator == 0:
                        continue
                    fingerprint = hashlib.sha256(
                        json.dumps(
                            {
                                "definition": definition.definition_sha256,
                                "window_days": definition.window_days,
                                "outcomes": sorted(outcomes),
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                    ).hexdigest()
                    already = await session.scalar(
                        select(func.count(MemoryMetricSnapshotModel.id)).where(
                            MemoryMetricSnapshotModel.definition_id == definition.id,
                            MemoryMetricSnapshotModel.window_end >= now - timedelta(days=1),
                        )
                    )
                    if already:
                        continue
                    session.add(
                        MemoryMetricSnapshotModel(
                            tenant_id=tenant_id,
                            definition_id=definition.id,
                            window_start=window_start,
                            window_end=now,
                            sample_size=ratio.denominator,
                            numerator=ratio.numerator,
                            denominator=ratio.denominator,
                            value=ratio.value,
                            sufficient_sample=ratio.sufficient_sample,
                            input_fingerprint=fingerprint,
                        )
                    )
                    await session.flush()
                    written += 1
        return written

    async def _metric_definition(
        self, session: AsyncSession, tenant_id: UUID, code: MetricCode
    ) -> MemoryMetricDefinitionModel:
        """The contract this metric was computed under, created on first use.

        Seeded here rather than in a migration because the minimum sample size
        follows configuration, and a tenant that changes it gets a new
        definition version rather than a silently different meaning for the
        same number.
        """
        settings = get_settings()
        digest = hashlib.sha256(
            json.dumps(
                {
                    "code": code.value,
                    "version": DEFINITION_VERSION,
                    "numerator": sorted(NUMERATOR[code]),
                    "denominator": sorted(DENOMINATOR[code]),
                    "window_days": _METRIC_WINDOW_DAYS,
                    "minimum_sample_size": settings.memory_minimum_sample_size,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        definition = await session.scalar(
            select(MemoryMetricDefinitionModel).where(
                MemoryMetricDefinitionModel.code == code.value,
                MemoryMetricDefinitionModel.version == DEFINITION_VERSION,
            )
        )
        if definition is not None:
            return definition
        definition = MemoryMetricDefinitionModel(
            tenant_id=tenant_id,
            code=code.value,
            version=DEFINITION_VERSION,
            definition_sha256=digest,
            window_days=_METRIC_WINDOW_DAYS,
            minimum_sample_size=settings.memory_minimum_sample_size,
            active=True,
        )
        session.add(definition)
        await session.flush()
        return definition

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
                    .where(
                        MemoryCandidateVersionModel.id == version_id,
                        MemoryCandidateVersionModel.is_synthetic.is_(False),
                    )
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
    def _feedback_response(
        item: FeedbackEntryModel,
        *,
        resource_label: str | None = None,
        actor_name: str | None = None,
    ) -> FeedbackResponse:
        return FeedbackResponse(
            id=item.id,
            resource_type=item.resource_type,
            resource_id=item.resource_id,
            resource_label=resource_label,
            actor_user_id=item.actor_user_id,
            actor_name=actor_name,
            outcome=item.outcome,
            reason=item.reason,
            is_synthetic=item.is_synthetic,
            occurred_at=item.occurred_at,
            created_at=item.created_at,
        )

    @staticmethod
    async def _author_names(session: AsyncSession, user_ids: set[UUID]) -> dict[UUID, str]:
        if not user_ids:
            return {}
        rows = (
            await session.execute(
                select(UserModel.id, UserModel.display_name).where(UserModel.id.in_(user_ids))
            )
        ).all()
        return {row[0]: row[1] for row in rows}

    @staticmethod
    async def _resource_labels(
        session: AsyncSession, items: list[FeedbackEntryModel]
    ) -> dict[UUID, str]:
        """Name each resource the way its own module names it.

        Resolved in one query per kind rather than one per row: a page of
        feedback about twenty-five incidents should not cost twenty-five
        round trips.
        """
        by_type: dict[str, set[UUID]] = {}
        for item in items:
            by_type.setdefault(item.resource_type, set()).add(item.resource_id)
        labels: dict[UUID, str] = {}

        if incident_ids := by_type.get("INCIDENT"):
            rows = (
                await session.execute(
                    select(IncidentModel.id, IncidentModel.code, IncidentModel.title).where(
                        IncidentModel.id.in_(incident_ids)
                    )
                )
            ).all()
            labels.update({row[0]: f"{row[1]} · {row[2]}" for row in rows})

        if finding_ids := by_type.get("FINDING"):
            rows = (
                await session.execute(
                    select(
                        FindingRevisionModel.id,
                        AlertReferenceModel.external_id,
                        AlertReferenceModel.title,
                    )
                    .join(
                        AlertReferenceModel,
                        AlertReferenceModel.id == FindingRevisionModel.alert_reference_id,
                    )
                    .where(FindingRevisionModel.id.in_(finding_ids))
                )
            ).all()
            labels.update({row[0]: f"{row[1]} · {row[2]}" for row in rows})

        if claim_ids := by_type.get("CLAIM"):
            claim_rows = (
                await session.execute(
                    select(ClaimModel.id, ClaimModel.statement).where(ClaimModel.id.in_(claim_ids))
                )
            ).all()
            labels.update({row[0]: row[1][:120] for row in claim_rows})

        # Proposals and executions are named by the action they carry; the
        # incident they belong to is what makes them recognisable.
        if proposal_ids := by_type.get("ACTION_PROPOSAL"):
            rows = (
                await session.execute(
                    select(
                        ActionProposalModel.id,
                        ActionProposalModel.action_type,
                        IncidentModel.code,
                    )
                    .join(IncidentModel, IncidentModel.id == ActionProposalModel.incident_id)
                    .where(ActionProposalModel.id.in_(proposal_ids))
                )
            ).all()
            labels.update({row[0]: f"{row[2]} · {row[1]}" for row in rows})

        if execution_ids := by_type.get("PLAYBOOK_EXECUTION"):
            execution_rows = (
                await session.execute(
                    select(PlaybookExecutionModel.id, IncidentModel.code)
                    .join(IncidentModel, IncidentModel.id == PlaybookExecutionModel.incident_id)
                    .where(PlaybookExecutionModel.id.in_(execution_ids))
                )
            ).all()
            labels.update({row[0]: f"{row[1]} · playbook" for row in execution_rows})

        return labels

    async def _candidate_response(
        self, session: AsyncSession, candidate: MemoryCandidateModel
    ) -> MemoryCandidateResponse:
        version = await session.scalar(
            select(MemoryCandidateVersionModel)
            .where(
                MemoryCandidateVersionModel.candidate_id == candidate.id,
                MemoryCandidateVersionModel.is_synthetic.is_(False),
            )
            .order_by(MemoryCandidateVersionModel.version.desc())
            .limit(1)
        )
        if version is None:
            raise GovernedMemoryNotFound("Memory candidate version was not found")
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
        authors = await self._author_names(
            session, {candidate.created_by_user_id, version.created_by_user_id}
        )
        return MemoryCandidateResponse(
            id=candidate.id,
            version_id=version.id,
            version=version.version,
            kind=candidate.kind,
            source_type=candidate.source_type,
            created_by_user_id=candidate.created_by_user_id,
            version_author_user_id=version.created_by_user_id,
            version_author_name=authors.get(version.created_by_user_id),
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
            .where(
                MemoryCandidateVersionModel.id == version_id,
                MemoryCandidateVersionModel.is_synthetic.is_(False),
            )
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
