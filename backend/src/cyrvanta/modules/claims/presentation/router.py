from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from cyrvanta.modules.claims.application.schemas import (
    AssessmentCreate,
    AssessmentResponse,
    ClaimCreate,
    ClaimResponse,
    PresentationCreate,
    PresentationResponse,
    RelationshipCreate,
    RelationshipResponse,
)
from cyrvanta.modules.claims.application.service import (
    ClaimConflict,
    ClaimNotFound,
    ClaimService,
)
from cyrvanta.shared.dependencies import (
    SecurityContext,
    authorize,
    get_security_context,
    require_permission,
)

router = APIRouter(tags=["claims"])
Service = Annotated[ClaimService, Depends(ClaimService)]
Authenticated = Annotated[SecurityContext, Depends(get_security_context)]
ClaimRead = Annotated[SecurityContext, Depends(require_permission("claim.read"))]
ClaimCreatePermission = Annotated[SecurityContext, Depends(require_permission("claim.create"))]
ClaimTranslate = Annotated[SecurityContext, Depends(require_permission("claim.translate"))]


def correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


def translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ClaimNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.get("/incidents/{incident_id}/claims", response_model=list[ClaimResponse])
async def list_claims(
    incident_id: UUID,
    context: ClaimRead,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
    claim_type: Annotated[str | None, Query(max_length=32)] = None,
) -> list[ClaimResponse]:
    try:
        return await service.list_claims(
            context.tenant_id,
            incident_id,
            limit=limit,
            offset=offset,
            query=q,
            claim_type=claim_type,
        )
    except ClaimNotFound as exc:
        raise translate_error(exc) from exc


@router.get("/claims/{claim_id}", response_model=ClaimResponse)
async def get_claim(claim_id: UUID, context: ClaimRead, service: Service) -> ClaimResponse:
    try:
        return await service.get_claim(context.tenant_id, claim_id)
    except ClaimNotFound as exc:
        raise translate_error(exc) from exc


@router.post(
    "/incidents/{incident_id}/claims",
    response_model=ClaimResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_claim(
    incident_id: UUID,
    payload: ClaimCreate,
    request: Request,
    context: ClaimCreatePermission,
    service: Service,
) -> ClaimResponse:
    try:
        return await service.create_human_claim(
            context.tenant_id,
            incident_id,
            context.user_id,
            payload,
            correlation_id(request),
        )
    except (ClaimNotFound, ClaimConflict, ValueError) as exc:
        raise translate_error(exc) from exc


@router.post(
    "/claims/{claim_id}/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assess_claim(
    claim_id: UUID,
    payload: AssessmentCreate,
    request: Request,
    context: Authenticated,
    service: Service,
) -> AssessmentResponse:
    await authorize(
        context,
        "claim.retract" if payload.outcome == "RETRACTED" else "claim.assess",
    )
    try:
        return await service.assess(
            context.tenant_id,
            claim_id,
            context.user_id,
            payload,
            correlation_id(request),
        )
    except (ClaimNotFound, ClaimConflict, ValueError) as exc:
        raise translate_error(exc) from exc


@router.post(
    "/claims/{claim_id}/relationships",
    response_model=RelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def relate_claim(
    claim_id: UUID,
    payload: RelationshipCreate,
    request: Request,
    context: ClaimCreatePermission,
    service: Service,
) -> RelationshipResponse:
    try:
        return await service.relate(
            context.tenant_id,
            claim_id,
            context.user_id,
            payload,
            correlation_id(request),
        )
    except (ClaimNotFound, ClaimConflict, ValueError) as exc:
        raise translate_error(exc) from exc


@router.post(
    "/claims/{claim_id}/presentations",
    response_model=PresentationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_presentation(
    claim_id: UUID,
    payload: PresentationCreate,
    request: Request,
    context: ClaimTranslate,
    service: Service,
) -> PresentationResponse:
    try:
        return await service.add_presentation(
            context.tenant_id,
            claim_id,
            context.user_id,
            payload,
            correlation_id(request),
        )
    except (ClaimNotFound, ClaimConflict, ValueError) as exc:
        raise translate_error(exc) from exc
