from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select

from cyrvanta.modules.ai_analysis.infrastructure.ollama import OllamaAIProvider
from cyrvanta.modules.threat_knowledge.application.schemas import (
    AttackTechniqueResponse,
    EnrichmentResponse,
)
from cyrvanta.modules.threat_knowledge.application.service import (
    EnrichmentUnavailable,
    ThreatEnrichmentService,
)
from cyrvanta.modules.threat_knowledge.infrastructure.models import (
    AttackObjectModel,
    AttackReleaseModel,
)
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.database import tenant_session
from cyrvanta.shared.dependencies import SecurityContext, require_permission
from cyrvanta.shared.infrastructure.event_store import SqlEventStore

router = APIRouter(tags=["threat-knowledge"])
CatalogRead = Annotated[SecurityContext, Depends(require_permission("mitre.catalog.read"))]
MappingRead = Annotated[SecurityContext, Depends(require_permission("mitre.mapping.read"))]
RiskRead = Annotated[SecurityContext, Depends(require_permission("risk.read"))]
RiskRecalculate = Annotated[SecurityContext, Depends(require_permission("risk.recalculate"))]
ExplanationRead = Annotated[SecurityContext, Depends(require_permission("explanation.read"))]
ExplanationGenerate = Annotated[
    SecurityContext, Depends(require_permission("explanation.generate"))
]


@router.get("/attack/techniques", response_model=list[AttackTechniqueResponse])
async def list_techniques(
    context: CatalogRead,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[AttackTechniqueResponse]:
    async with tenant_session(context.tenant_id) as session:
        statement = (
            select(AttackObjectModel, AttackReleaseModel)
            .join(AttackReleaseModel, AttackReleaseModel.id == AttackObjectModel.release_id)
            .where(
                AttackReleaseModel.status == "ACTIVE",
                AttackObjectModel.object_type == "attack-pattern",
            )
            .order_by(AttackObjectModel.external_id)
            .limit(limit)
            .offset(offset)
        )
        if q:
            pattern = f"%{q.casefold()}%"
            statement = statement.where(
                or_(
                    func.lower(AttackObjectModel.external_id).like(pattern),
                    func.lower(AttackObjectModel.name_en).like(pattern),
                )
            )
        rows = (await session.execute(statement)).all()
        return [
            AttackTechniqueResponse(
                id=item.id,
                release_version=release.version,
                external_id=item.external_id or "",
                name_en=item.name_en or "",
                tactic_codes=list(item.tactic_codes),
                is_subtechnique=item.is_subtechnique,
                revoked=item.revoked,
                deprecated=item.deprecated,
            )
            for item, release in rows
        ]


@router.get(
    "/incidents/{incident_id}/enrichment",
    response_model=EnrichmentResponse,
)
async def get_enrichment(
    incident_id: UUID,
    context: RiskRead,
    _mapping_context: MappingRead,
    _explanation_context: ExplanationRead,
) -> EnrichmentResponse:
    async with tenant_session(context.tenant_id) as session:
        service = ThreatEnrichmentService(
            session,
            SqlEventStore(
                session_factory=None,  # type: ignore[arg-type]
                max_payload_bytes=get_settings().event_max_payload_bytes,
            ).recorder(session),
        )
        try:
            return await service.get(context.tenant_id, incident_id)
        except EnrichmentUnavailable as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post(
    "/incidents/{incident_id}/risk-assessments",
    response_model=EnrichmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def recalculate_risk(
    incident_id: UUID,
    request: Request,
    context: RiskRecalculate,
    _mapping_context: MappingRead,
    _explanation_context: ExplanationRead,
) -> EnrichmentResponse:
    settings = get_settings()
    async with tenant_session(context.tenant_id) as session:
        events = SqlEventStore(
            session_factory=None,  # type: ignore[arg-type]
            max_payload_bytes=settings.event_max_payload_bytes,
        ).recorder(session)
        try:
            return await ThreatEnrichmentService(session, events).enrich(
                context.tenant_id,
                incident_id,
                UUID(request.state.correlation_id),
            )
        except EnrichmentUnavailable as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post(
    "/incidents/{incident_id}/explanations",
    response_model=EnrichmentResponse,
)
async def generate_explanation(
    incident_id: UUID,
    request: Request,
    context: ExplanationGenerate,
    _mapping_context: MappingRead,
    _risk_context: RiskRead,
) -> EnrichmentResponse:
    settings = get_settings()
    async with tenant_session(context.tenant_id) as session:
        events = SqlEventStore(
            session_factory=None,  # type: ignore[arg-type]
            max_payload_bytes=settings.event_max_payload_bytes,
        ).recorder(session)
        service = ThreatEnrichmentService(session, events)
        try:
            current = await service.get(context.tenant_id, incident_id)
        except EnrichmentUnavailable as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    deterministic_es = next(
        item.text
        for item in current.explanations
        if item.locale == "es" and item.mode == "DETERMINISTIC"
    )
    deterministic_en = next(
        item.text
        for item in current.explanations
        if item.locale == "en" and item.mode == "DETERMINISTIC"
    )
    draft = await OllamaAIProvider(settings).redact_explanation(deterministic_es, deterministic_en)
    async with tenant_session(context.tenant_id) as session:
        events = SqlEventStore(
            session_factory=None,  # type: ignore[arg-type]
            max_payload_bytes=settings.event_max_payload_bytes,
        ).recorder(session)
        service = ThreatEnrichmentService(session, events)
        await service.record_ai_redaction(
            context.tenant_id,
            incident_id,
            current.risk.id,
            UUID(request.state.correlation_id),
            draft,
        )
        return await service.get(context.tenant_id, incident_id)
