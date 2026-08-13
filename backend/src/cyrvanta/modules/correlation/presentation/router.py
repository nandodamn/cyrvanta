from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from cyrvanta.modules.correlation.application.query_service import (
    CorrelationNotFound,
    CorrelationQueryService,
)
from cyrvanta.modules.correlation.application.schemas import (
    CanonicalDemoResponse,
    CorrelationResponse,
)
from cyrvanta.shared.dependencies import SecurityContext, require_permission

router = APIRouter(tags=["correlation"])
Service = Annotated[CorrelationQueryService, Depends(CorrelationQueryService)]
CorrelationRead = Annotated[SecurityContext, Depends(require_permission("correlation.read"))]
CorrelationEvaluate = Annotated[
    SecurityContext, Depends(require_permission("correlation.evaluate"))
]


@router.get(
    "/incidents/{incident_id}/correlations",
    response_model=list[CorrelationResponse],
)
async def list_incident_correlations(
    incident_id: UUID,
    context: CorrelationRead,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> list[CorrelationResponse]:
    try:
        return await service.list_for_incident(
            context.tenant_id, incident_id, limit=limit, offset=offset
        )
    except CorrelationNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found") from exc


@router.get("/correlations/{match_id}", response_model=CorrelationResponse)
async def get_correlation(
    match_id: UUID,
    context: CorrelationRead,
    service: Service,
) -> CorrelationResponse:
    try:
        return await service.get(context.tenant_id, match_id)
    except CorrelationNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found") from exc
