from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.claims.application.schemas import (
    AssessmentCreate,
    AssessmentResponse,
    ClaimCreate,
    ClaimResponse,
    EvidenceInput,
    EvidenceResponse,
    PresentationCreate,
    PresentationResponse,
    RelationshipCreate,
    RelationshipResponse,
)
from cyrvanta.modules.claims.domain.models import (
    AssessmentOutcome,
    Claim,
    ClaimAssessment,
    ClaimOriginType,
    ClaimRelationshipType,
    ClaimType,
    EvidenceLink,
    EvidenceRelationship,
    EvidenceType,
    derive_presentation_state,
)
from cyrvanta.modules.claims.infrastructure.models import (
    ClaimAssessmentModel,
    ClaimEvidenceLinkModel,
    ClaimModel,
    ClaimPresentationModel,
    ClaimRelationshipModel,
)
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
from cyrvanta.modules.incident.infrastructure.models import (
    IncidentAlertModel,
    IncidentModel,
    IncidentTimelineModel,
)
from cyrvanta.modules.integrations.infrastructure.models import FindingRevisionModel
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.database import SessionFactory, tenant_session
from cyrvanta.shared.domain.events import DomainEvent
from cyrvanta.shared.infrastructure.event_store import SqlEventStore

CLAIM_CREATED_EVENT = "knowledge.claim.created"
CLAIM_ASSESSED_EVENT = "knowledge.claim.assessed"
CLAIM_RELATED_EVENT = "knowledge.claim.related"
CLAIM_PRESENTATION_CREATED_EVENT = "knowledge.claim.presentation.created"


class ClaimNotFound(Exception):
    pass


class ClaimConflict(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AnalysisClaimInput:
    claim_type: ClaimType
    statement: str
    language_code: str
    confidence: float
    explanation: str
    presentation_locale: str | None = None
    presentation_text: str | None = None
    claim_slot: str | None = None


class ClaimService:
    def __init__(self) -> None:
        settings = get_settings()
        self._events = SqlEventStore(SessionFactory, settings.event_max_payload_bytes)

    async def list_claims(
        self,
        tenant_id: UUID,
        incident_id: UUID,
        *,
        limit: int,
        offset: int,
        query: str | None = None,
        claim_type: str | None = None,
    ) -> list[ClaimResponse]:
        async with tenant_session(tenant_id) as session:
            await self._incident(session, incident_id)
            statement = select(ClaimModel).where(ClaimModel.incident_id == incident_id)
            if query and (normalized := query.strip()):
                escaped = (
                    normalized.replace("\\", "\\\\")
                    .replace("%", "\\%")
                    .replace("_", "\\_")
                )
                statement = statement.where(
                    or_(
                        ClaimModel.statement.ilike(f"%{escaped}%", escape="\\"),
                        ClaimModel.claim_type.ilike(f"%{escaped}%", escape="\\"),
                        ClaimModel.origin_type.ilike(f"%{escaped}%", escape="\\"),
                    )
                )
            if claim_type is not None:
                statement = statement.where(ClaimModel.claim_type == claim_type)
            claims = list(
                (
                    await session.scalars(
                        statement.order_by(
                            ClaimModel.created_at.desc(), ClaimModel.id.desc()
                        )
                        .offset(offset)
                        .limit(limit)
                    )
                ).all()
            )
            return [await self._view(session, item) for item in claims]

    async def get_claim(self, tenant_id: UUID, claim_id: UUID) -> ClaimResponse:
        async with tenant_session(tenant_id) as session:
            return await self._view(session, await self._claim(session, claim_id))

    async def create_human_claim(
        self,
        tenant_id: UUID,
        incident_id: UUID,
        actor_user_id: UUID,
        payload: ClaimCreate,
        correlation_id: UUID,
    ) -> ClaimResponse:
        async with tenant_session(tenant_id) as session:
            incident = await self._incident(session, incident_id)
            claim_type = ClaimType(payload.claim_type)
            if claim_type is ClaimType.DERIVED_FACT and (
                not payload.method_code or not payload.method_version
            ):
                raise ClaimConflict("Derived facts require method code and version")
            if claim_type is ClaimType.FACT and not any(
                EvidenceType(item.evidence_type)
                in {
                    EvidenceType.FINDING_REVISION,
                    EvidenceType.ALERT_REFERENCE,
                    EvidenceType.INCIDENT_TIMELINE_ENTRY,
                    EvidenceType.AUDIT_EVENT,
                }
                for item in payload.evidence
            ):
                raise ClaimConflict("Facts require at least one direct evidence source")
            claim = Claim(
                claim_id=uuid4(),
                tenant_id=tenant_id,
                incident_id=incident_id,
                claim_type=claim_type,
                statement=payload.statement,
                language_code=payload.language_code,
                confidence=payload.confidence,
                origin_type=ClaimOriginType.HUMAN,
                origin_actor_user_id=actor_user_id,
                origin_code=payload.method_code,
                origin_version=payload.method_version,
                provider=None,
                model=None,
                prompt_template_version=None,
                output_schema_version=None,
                input_fingerprint=None,
                explanation=payload.explanation,
                validation_criteria=payload.validation_criteria,
                missing_evidence=tuple(payload.missing_evidence),
                is_simulated=incident.is_simulated,
                correlation_id=correlation_id,
                causation_id=None,
                created_at=datetime.now(UTC),
            )
            model = await self._insert_claim(
                session,
                claim,
                payload.evidence,
                actor_user_id=actor_user_id,
            )
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                "claim.created",
                model.id,
                correlation_id,
                {"claim_type": model.claim_type},
            )
            return await self._view(session, model)

    async def assess(
        self,
        tenant_id: UUID,
        claim_id: UUID,
        actor_user_id: UUID,
        payload: AssessmentCreate,
        correlation_id: UUID,
    ) -> AssessmentResponse:
        assessment = ClaimAssessment(
            outcome=AssessmentOutcome(payload.outcome),
            evaluator_user_id=actor_user_id,
            explanation=payload.explanation,
        )
        async with tenant_session(tenant_id) as session:
            claim = await self._claim(session, claim_id)
            if assessment.outcome is AssessmentOutcome.RETRACTED:
                if claim.origin_type != ClaimOriginType.HUMAN.value:
                    raise ClaimConflict("Only a human claim can be retracted")
                if claim.origin_actor_user_id != actor_user_id:
                    raise ClaimConflict("Only the human author can retract this claim")
            elif claim.origin_actor_user_id == actor_user_id:
                raise ClaimConflict("A human author cannot assess their own claim")
            model = ClaimAssessmentModel(
                tenant_id=tenant_id,
                claim_id=claim_id,
                outcome=assessment.outcome.value,
                evaluator_user_id=actor_user_id,
                explanation=assessment.explanation,
                correlation_id=correlation_id,
            )
            session.add(model)
            await session.flush()
            await self._record_event(
                session,
                event_name=CLAIM_ASSESSED_EVENT,
                tenant_id=tenant_id,
                incident_id=claim.incident_id,
                claim_id=claim_id,
                correlation_id=correlation_id,
                payload={"outcome": model.outcome},
            )
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                "claim.assessed",
                claim_id,
                correlation_id,
                {"outcome": model.outcome},
            )
            return AssessmentResponse(
                id=model.id,
                claim_id=claim_id,
                outcome=model.outcome,
                evaluator_user_id=model.evaluator_user_id,
                explanation=model.explanation,
                created_at=model.created_at or datetime.now(UTC),
            )

    async def relate(
        self,
        tenant_id: UUID,
        source_claim_id: UUID,
        actor_user_id: UUID,
        payload: RelationshipCreate,
        correlation_id: UUID,
    ) -> RelationshipResponse:
        relationship_type = ClaimRelationshipType(payload.relationship_type)
        if source_claim_id == payload.target_claim_id:
            raise ClaimConflict("A claim cannot relate to itself")
        async with tenant_session(tenant_id) as session:
            source = await self._claim(session, source_claim_id)
            target = await self._claim(session, payload.target_claim_id)
            if source.incident_id != target.incident_id:
                raise ClaimConflict("Claims must belong to the same incident")
            if relationship_type in {
                ClaimRelationshipType.DERIVED_FROM,
                ClaimRelationshipType.SUPERSEDES,
            } and await self._would_cycle(
                session,
                tenant_id,
                source_claim_id,
                payload.target_claim_id,
                relationship_type,
            ):
                raise ClaimConflict("Claim relationship would create a cycle")
            model = ClaimRelationshipModel(
                tenant_id=tenant_id,
                source_claim_id=source_claim_id,
                target_claim_id=payload.target_claim_id,
                relationship_type=relationship_type.value,
                created_by_user_id=actor_user_id,
                producer="claim_api",
                correlation_id=correlation_id,
            )
            session.add(model)
            try:
                await session.flush()
            except Exception as exc:
                raise ClaimConflict("Claim relationship already exists") from exc
            await self._record_event(
                session,
                event_name=CLAIM_RELATED_EVENT,
                tenant_id=tenant_id,
                incident_id=source.incident_id,
                claim_id=source_claim_id,
                correlation_id=correlation_id,
                payload={
                    "target_claim_id": str(payload.target_claim_id),
                    "relationship_type": relationship_type.value,
                },
            )
            if relationship_type in {
                ClaimRelationshipType.CONTRADICTS,
                ClaimRelationshipType.SUPERSEDES,
            }:
                self._audit(
                    session,
                    tenant_id,
                    actor_user_id,
                    "claim.related",
                    source_claim_id,
                    correlation_id,
                    {
                        "target_claim_id": str(payload.target_claim_id),
                        "relationship_type": relationship_type.value,
                    },
                )
            return RelationshipResponse(
                id=model.id,
                source_claim_id=model.source_claim_id,
                target_claim_id=model.target_claim_id,
                relationship_type=model.relationship_type,
                created_at=model.created_at or datetime.now(UTC),
            )

    async def add_presentation(
        self,
        tenant_id: UUID,
        claim_id: UUID,
        actor_user_id: UUID,
        payload: PresentationCreate,
        correlation_id: UUID,
    ) -> PresentationResponse:
        async with tenant_session(tenant_id) as session:
            claim = await self._claim(session, claim_id)
            version = int(
                await session.scalar(
                    select(func.coalesce(func.max(ClaimPresentationModel.version), 0) + 1)
                    .where(ClaimPresentationModel.claim_id == claim_id)
                    .where(ClaimPresentationModel.locale == payload.locale)
                )
                or 1
            )
            model = ClaimPresentationModel(
                tenant_id=tenant_id,
                claim_id=claim_id,
                locale=payload.locale,
                text=payload.text,
                version=version,
                origin_type=ClaimOriginType.HUMAN.value,
                origin_actor_user_id=actor_user_id,
                correlation_id=correlation_id,
            )
            session.add(model)
            await session.flush()
            await self._record_event(
                session,
                event_name=CLAIM_PRESENTATION_CREATED_EVENT,
                tenant_id=tenant_id,
                incident_id=claim.incident_id,
                claim_id=claim_id,
                correlation_id=correlation_id,
                payload={"locale": payload.locale, "version": version},
            )
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                "claim.presentation.created",
                claim_id,
                correlation_id,
                {"locale": payload.locale, "version": version},
            )
            return PresentationResponse(
                id=model.id,
                claim_id=claim_id,
                locale=model.locale,
                text=model.text,
                version=model.version,
                created_at=model.created_at or datetime.now(UTC),
            )

    async def record_analysis(
        self,
        *,
        tenant_id: UUID,
        incident_id: UUID,
        correlation_id: UUID,
        provider: str,
        model: str,
        mode: str,
        input_fingerprint: str,
        claims: tuple[AnalysisClaimInput, ...],
    ) -> tuple[UUID, ...]:
        created: list[UUID] = []
        async with tenant_session(tenant_id) as session:
            incident = await self._incident(session, incident_id)
            for item in claims:
                origin_type = (
                    ClaimOriginType.AI
                    if provider == "ollama"
                    else ClaimOriginType.RULE
                )
                origin_code = (
                    f"incident-analysis:{item.claim_slot}"
                    if item.claim_slot
                    else (
                        None
                        if origin_type is ClaimOriginType.AI
                        else "incident-analysis"
                    )
                )
                if item.claim_slot == "summary":
                    legacy_summary = (
                        ClaimModel.statement.not_ilike("MITRE ATT&CK technique %")
                    )
                    existing_summary = await session.scalar(
                        select(ClaimModel.id)
                        .where(ClaimModel.incident_id == incident_id)
                        .where(ClaimModel.claim_type == item.claim_type.value)
                        .where(ClaimModel.input_fingerprint == input_fingerprint)
                        .where(
                            or_(
                                ClaimModel.origin_code == origin_code,
                                (
                                    ClaimModel.origin_code.is_(None)
                                    if origin_type is ClaimOriginType.AI
                                    else ClaimModel.origin_code == "incident-analysis"
                                ),
                            )
                        )
                        .where(legacy_summary)
                        .limit(1)
                    )
                    if existing_summary is not None:
                        continue
                idempotency_key = sha256(
                    "|".join(
                        (
                            str(tenant_id),
                            str(incident_id),
                            input_fingerprint,
                            provider,
                            model,
                            item.claim_type.value,
                            item.language_code,
                            item.claim_slot or item.statement,
                        )
                    ).encode("utf-8")
                ).hexdigest()
                claim = Claim(
                    claim_id=uuid4(),
                    tenant_id=tenant_id,
                    incident_id=incident_id,
                    claim_type=item.claim_type,
                    statement=item.statement,
                    language_code=item.language_code,
                    confidence=item.confidence,
                    origin_type=origin_type,
                    origin_actor_user_id=None,
                    origin_code=origin_code,
                    origin_version=(
                        None if origin_type is ClaimOriginType.AI else "1"
                    ),
                    provider=provider if origin_type is ClaimOriginType.AI else None,
                    model=model if origin_type is ClaimOriginType.AI else None,
                    prompt_template_version=(
                        "incident-summary-v1"
                        if origin_type is ClaimOriginType.AI
                        else None
                    ),
                    output_schema_version=(
                        "summary-v1" if origin_type is ClaimOriginType.AI else None
                    ),
                    input_fingerprint=input_fingerprint,
                    explanation=item.explanation,
                    validation_criteria=None,
                    missing_evidence=(),
                    is_simulated=incident.is_simulated or mode == "simulated",
                    correlation_id=correlation_id,
                    causation_id=None,
                    created_at=datetime.now(UTC),
                    idempotency_key=idempotency_key,
                )
                inserted_id = await session.scalar(
                    pg_insert(ClaimModel)
                    .values(self._claim_values(claim))
                    .on_conflict_do_nothing(constraint="uq_claims_idempotency")
                    .returning(ClaimModel.id)
                )
                if not isinstance(inserted_id, UUID):
                    continue
                evidence = EvidenceInput(
                    evidence_type="INCIDENT",
                    evidence_id=incident_id,
                    relationship="SUPPORTS",
                )
                await self._insert_evidence(
                    session,
                    claim,
                    inserted_id,
                    evidence,
                    actor_user_id=None,
                )
                if item.presentation_locale and item.presentation_text:
                    session.add(
                        ClaimPresentationModel(
                            tenant_id=tenant_id,
                            claim_id=inserted_id,
                            locale=item.presentation_locale,
                            text=item.presentation_text,
                            version=1,
                            origin_type=origin_type.value,
                            provider=provider if origin_type is ClaimOriginType.AI else None,
                            model=model if origin_type is ClaimOriginType.AI else None,
                            correlation_id=correlation_id,
                        )
                    )
                await self._record_event(
                    session,
                    event_name=CLAIM_CREATED_EVENT,
                    tenant_id=tenant_id,
                    incident_id=incident_id,
                    claim_id=inserted_id,
                    correlation_id=correlation_id,
                    payload={
                        "claim_type": item.claim_type.value,
                        "origin_type": origin_type.value,
                        "schema_version": 1,
                    },
                )
                created.append(inserted_id)
        return tuple(created)

    async def record_correlation_match(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        incident_id: UUID,
        match_id: UUID,
        rule_code: str,
        rule_version: str,
        score: int,
        input_fingerprint: str,
        revision_ids: tuple[UUID, ...],
        is_simulated: bool,
        correlation_id: UUID,
        causation_id: UUID,
    ) -> UUID:
        await self._incident(session, incident_id)
        idempotency_key = sha256(
            f"{tenant_id}|{incident_id}|correlation|{match_id}".encode()
        ).hexdigest()
        existing = await session.scalar(
            select(ClaimModel.id).where(
                ClaimModel.incident_id == incident_id,
                ClaimModel.idempotency_key == idempotency_key,
            )
        )
        if isinstance(existing, UUID):
            return existing
        claim = Claim(
            claim_id=uuid4(),
            tenant_id=tenant_id,
            incident_id=incident_id,
            claim_type=ClaimType.DERIVED_FACT,
            statement=(
                f"Rule {rule_code} version {rule_version} correlated "
                f"{len(revision_ids)} finding revisions with score {score}."
            ),
            language_code="und",
            confidence=None,
            origin_type=ClaimOriginType.RULE,
            origin_actor_user_id=None,
            origin_code=rule_code,
            origin_version=rule_version,
            provider=None,
            model=None,
            prompt_template_version=None,
            output_schema_version=None,
            input_fingerprint=input_fingerprint,
            explanation=(
                f"Deterministic correlation match {match_id}; "
                "the score is not risk or confidence."
            ),
            validation_criteria=None,
            missing_evidence=(),
            is_simulated=is_simulated,
            correlation_id=correlation_id,
            causation_id=causation_id,
            created_at=datetime.now(UTC),
            idempotency_key=idempotency_key,
        )
        model = await self._insert_claim(
            session,
            claim,
            [
                EvidenceInput(
                    evidence_type="FINDING_REVISION",
                    evidence_id=revision_id,
                    relationship="SUPPORTS",
                )
                for revision_id in revision_ids
            ],
            actor_user_id=None,
        )
        return model.id

    async def _insert_claim(
        self,
        session: AsyncSession,
        claim: Claim,
        evidence: list[EvidenceInput],
        *,
        actor_user_id: UUID | None,
    ) -> ClaimModel:
        model = ClaimModel(**self._claim_values(claim))
        session.add(model)
        await session.flush()
        for item in evidence:
            await self._insert_evidence(
                session, claim, model.id, item, actor_user_id=actor_user_id
            )
        await self._record_event(
            session,
            event_name=CLAIM_CREATED_EVENT,
            tenant_id=claim.tenant_id,
            incident_id=claim.incident_id,
            claim_id=model.id,
            correlation_id=claim.correlation_id,
            payload={
                "claim_type": claim.claim_type.value,
                "origin_type": claim.origin_type.value,
                "schema_version": claim.schema_version,
            },
            causation_id=claim.causation_id,
        )
        return model

    @staticmethod
    def _claim_values(claim: Claim) -> dict[str, object]:
        return {
            "id": claim.claim_id,
            "tenant_id": claim.tenant_id,
            "incident_id": claim.incident_id,
            "claim_type": claim.claim_type.value,
            "statement": claim.statement,
            "language_code": claim.language_code,
            "confidence": claim.confidence,
            "origin_type": claim.origin_type.value,
            "origin_actor_user_id": claim.origin_actor_user_id,
            "origin_code": claim.origin_code,
            "origin_version": claim.origin_version,
            "provider": claim.provider,
            "model": claim.model,
            "prompt_template_version": claim.prompt_template_version,
            "output_schema_version": claim.output_schema_version,
            "input_fingerprint": claim.input_fingerprint,
            "explanation": claim.explanation,
            "validation_criteria": claim.validation_criteria,
            "missing_evidence": list(claim.missing_evidence),
            "is_simulated": claim.is_simulated,
            "correlation_id": claim.correlation_id,
            "causation_id": claim.causation_id,
            "idempotency_key": claim.idempotency_key,
            "schema_version": claim.schema_version,
            "created_at": claim.created_at,
        }

    async def _insert_evidence(
        self,
        session: AsyncSession,
        claim: Claim,
        claim_id: UUID,
        item: EvidenceInput,
        *,
        actor_user_id: UUID | None,
    ) -> None:
        evidence = EvidenceLink(
            evidence_type=EvidenceType(item.evidence_type),
            evidence_id=item.evidence_id,
            relationship=EvidenceRelationship(item.relationship),
            evidence_sha256=item.evidence_sha256,
        )
        await self._validate_evidence(session, claim, evidence)
        session.add(
            ClaimEvidenceLinkModel(
                tenant_id=claim.tenant_id,
                claim_id=claim_id,
                evidence_type=evidence.evidence_type.value,
                evidence_id=evidence.evidence_id,
                relationship=evidence.relationship.value,
                evidence_sha256=evidence.evidence_sha256,
                created_by_user_id=actor_user_id,
                correlation_id=claim.correlation_id,
            )
        )

    async def _validate_evidence(
        self, session: AsyncSession, claim: Claim, evidence: EvidenceLink
    ) -> None:
        exists = False
        if evidence.evidence_type is EvidenceType.INCIDENT:
            exists = evidence.evidence_id == claim.incident_id
        elif evidence.evidence_type is EvidenceType.CLAIM:
            target = await session.get(ClaimModel, evidence.evidence_id)
            exists = target is not None and target.incident_id == claim.incident_id
        elif evidence.evidence_type is EvidenceType.ALERT_REFERENCE:
            exists = bool(
                await session.scalar(
                    select(IncidentAlertModel.id)
                    .where(IncidentAlertModel.incident_id == claim.incident_id)
                    .where(IncidentAlertModel.alert_id == evidence.evidence_id)
                )
            )
        elif evidence.evidence_type is EvidenceType.FINDING_REVISION:
            exists = bool(
                await session.scalar(
                    select(FindingRevisionModel.id)
                    .join(
                        IncidentAlertModel,
                        IncidentAlertModel.alert_id
                        == FindingRevisionModel.alert_reference_id,
                    )
                    .where(IncidentAlertModel.incident_id == claim.incident_id)
                    .where(FindingRevisionModel.id == evidence.evidence_id)
                )
            )
        elif evidence.evidence_type is EvidenceType.INCIDENT_TIMELINE_ENTRY:
            exists = bool(
                await session.scalar(
                    select(IncidentTimelineModel.id)
                    .where(IncidentTimelineModel.incident_id == claim.incident_id)
                    .where(IncidentTimelineModel.id == evidence.evidence_id)
                )
            )
        elif evidence.evidence_type is EvidenceType.AUDIT_EVENT:
            exists = bool(
                await session.scalar(
                    select(AuditEventModel.id)
                    .where(AuditEventModel.resource_id == claim.incident_id)
                    .where(AuditEventModel.id == evidence.evidence_id)
                )
            )
        if not exists:
            raise ClaimConflict("Evidence is unavailable for this incident")

    async def _view(self, session: AsyncSession, claim: ClaimModel) -> ClaimResponse:
        evidence_models = list(
            (
                await session.scalars(
                    select(ClaimEvidenceLinkModel)
                    .where(ClaimEvidenceLinkModel.claim_id == claim.id)
                    .order_by(ClaimEvidenceLinkModel.created_at, ClaimEvidenceLinkModel.id)
                )
            ).all()
        )
        assessments = list(
            (
                await session.scalars(
                    select(ClaimAssessmentModel)
                    .where(ClaimAssessmentModel.claim_id == claim.id)
                    .order_by(
                        ClaimAssessmentModel.created_at, ClaimAssessmentModel.id
                    )
                )
            ).all()
        )
        superseded = bool(
            await session.scalar(
                select(ClaimRelationshipModel.id)
                .where(ClaimRelationshipModel.target_claim_id == claim.id)
                .where(
                    ClaimRelationshipModel.relationship_type
                    == ClaimRelationshipType.SUPERSEDES.value
                )
                .limit(1)
            )
        )
        contradicted = bool(
            await session.scalar(
                select(ClaimRelationshipModel.id)
                .where(
                    or_(
                        ClaimRelationshipModel.source_claim_id == claim.id,
                        ClaimRelationshipModel.target_claim_id == claim.id,
                    )
                )
                .where(
                    ClaimRelationshipModel.relationship_type
                    == ClaimRelationshipType.CONTRADICTS.value
                )
                .limit(1)
            )
        )
        latest_presentations = (
            await session.execute(
                text(
                    """
                    SELECT DISTINCT ON (locale) locale, text
                    FROM claim_presentations
                    WHERE tenant_id = :tenant_id AND claim_id = :claim_id
                    ORDER BY locale, version DESC
                    """
                ),
                {"tenant_id": claim.tenant_id, "claim_id": claim.id},
            )
        ).all()
        outcomes = [AssessmentOutcome(item.outcome) for item in assessments]
        state = derive_presentation_state(
            latest_outcome=outcomes[-1] if outcomes else None,
            superseded=superseded,
            contradicted=contradicted,
            conflicting_assessments=len(set(outcomes)) > 1,
        )
        return ClaimResponse(
            id=claim.id,
            incident_id=claim.incident_id,
            claim_type=claim.claim_type,
            statement=claim.statement,
            language_code=claim.language_code,
            confidence=float(claim.confidence) if claim.confidence is not None else None,
            origin_type=claim.origin_type,
            origin_actor_user_id=claim.origin_actor_user_id,
            origin_code=claim.origin_code,
            origin_version=claim.origin_version,
            provider=claim.provider,
            model=claim.model,
            explanation=claim.explanation,
            validation_criteria=claim.validation_criteria,
            missing_evidence=list(claim.missing_evidence),
            is_simulated=claim.is_simulated,
            state=state.value,
            evidence=[
                EvidenceResponse(
                    evidence_type=item.evidence_type,
                    evidence_id=item.evidence_id,
                    relationship=item.relationship,
                    evidence_sha256=item.evidence_sha256,
                )
                for item in evidence_models
            ],
            presentations={row.locale: row.text for row in latest_presentations},
            created_at=claim.created_at,
        )

    async def _record_event(
        self,
        session: AsyncSession,
        *,
        event_name: str,
        tenant_id: UUID,
        incident_id: UUID,
        claim_id: UUID,
        correlation_id: UUID,
        payload: dict[str, object],
        causation_id: UUID | None = None,
    ) -> None:
        await self._events.recorder(session).add(
            DomainEvent.create(
                event_name=event_name,
                tenant_id=tenant_id,
                aggregate_type="claim",
                aggregate_id=claim_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                producer="claim_ledger",
                payload={
                    "claim_id": str(claim_id),
                    "incident_id": str(incident_id),
                    **payload,
                },
            )
        )

    @staticmethod
    async def _incident(session: AsyncSession, incident_id: UUID) -> IncidentModel:
        incident = await session.get(IncidentModel, incident_id)
        if incident is None:
            raise ClaimNotFound
        return incident

    @staticmethod
    async def _claim(session: AsyncSession, claim_id: UUID) -> ClaimModel:
        claim = await session.get(ClaimModel, claim_id)
        if claim is None:
            raise ClaimNotFound
        return claim

    @staticmethod
    async def _would_cycle(
        session: AsyncSession,
        tenant_id: UUID,
        source_claim_id: UUID,
        target_claim_id: UUID,
        relationship_type: ClaimRelationshipType,
    ) -> bool:
        return bool(
            await session.scalar(
                text(
                    """
                    WITH RECURSIVE reachable(claim_id) AS (
                      SELECT target_claim_id
                      FROM claim_relationships
                      WHERE tenant_id = :tenant_id
                        AND source_claim_id = :target_claim_id
                        AND relationship_type = :relationship_type
                      UNION
                      SELECT r.target_claim_id
                      FROM claim_relationships r
                      JOIN reachable p ON r.source_claim_id = p.claim_id
                      WHERE r.tenant_id = :tenant_id
                        AND r.relationship_type = :relationship_type
                    )
                    SELECT EXISTS (
                      SELECT 1 FROM reachable WHERE claim_id = :source_claim_id
                    )
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "source_claim_id": source_claim_id,
                    "target_claim_id": target_claim_id,
                    "relationship_type": relationship_type.value,
                },
            )
        )

    @staticmethod
    def _audit(
        session: AsyncSession,
        tenant_id: UUID,
        actor_user_id: UUID,
        action: str,
        resource_id: UUID,
        correlation_id: UUID,
        details: dict[str, object],
    ) -> None:
        session.add(
            AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action=action,
                resource_type="claim",
                resource_id=resource_id,
                outcome="success",
                correlation_id=correlation_id,
                details=details,
            )
        )
