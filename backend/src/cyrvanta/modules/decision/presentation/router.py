from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from cyrvanta.modules.decision.application.schemas import (
    ActionProposalCreate,
    ActionProposalList,
    ActionProposalResponse,
    ApprovalDecisionCreate,
)
from cyrvanta.modules.decision.application.service import (
    DecisionConflict,
    DecisionNotFound,
    DecisionService,
)
from cyrvanta.shared.dependencies import SecurityContext, require_permission

router = APIRouter(tags=["response-decisions"])
ResponseReader = Annotated[SecurityContext, Depends(require_permission("response.read"))]
ResponseRequester = Annotated[
    SecurityContext, Depends(require_permission("response.request"))
]
ResponseApprover = Annotated[
    SecurityContext, Depends(require_permission("response.approve"))
]
ResponseRevoker = Annotated[
    SecurityContext, Depends(require_permission("response.revoke"))
]


def correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


def translate(exc: Exception) -> HTTPException:
    if isinstance(exc, DecisionNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.post(
    "/response-proposals",
    response_model=ActionProposalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_proposal(
    payload: ActionProposalCreate,
    request: Request,
    context: ResponseRequester,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> ActionProposalResponse:
    try:
        return await DecisionService().create_proposal(
            tenant_id=context.tenant_id,
            requester_user_id=context.user_id,
            payload=payload,
            correlation_id=correlation_id(request),
            idempotency_key=idempotency_key,
        )
    except (DecisionConflict, DecisionNotFound, ValueError) as exc:
        raise translate(exc) from exc


@router.get("/response-proposals", response_model=ActionProposalList)
async def list_proposals(
    context: ResponseReader,
    incident_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> ActionProposalList:
    return await DecisionService().list_proposals(
        context.tenant_id, incident_id=incident_id, limit=limit, offset=offset
    )


@router.get("/response-proposals/{proposal_id}", response_model=ActionProposalResponse)
async def get_proposal(
    proposal_id: UUID, context: ResponseReader
) -> ActionProposalResponse:
    try:
        return await DecisionService().get_proposal(context.tenant_id, proposal_id)
    except DecisionNotFound as exc:
        raise translate(exc) from exc


@router.post(
    "/approval-requests/{approval_request_id}/decisions",
    response_model=ActionProposalResponse,
)
async def decide(
    approval_request_id: UUID,
    payload: ApprovalDecisionCreate,
    request: Request,
    context: ResponseApprover,
) -> ActionProposalResponse:
    try:
        return await DecisionService().decide(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            approval_request_id=approval_request_id,
            payload=payload,
            correlation_id=correlation_id(request),
        )
    except (DecisionConflict, DecisionNotFound) as exc:
        raise translate(exc) from exc


@router.post(
    "/response-authorizations/{authorization_id}/revoke",
    response_model=ActionProposalResponse,
)
async def revoke(
    authorization_id: UUID,
    request: Request,
    context: ResponseRevoker,
) -> ActionProposalResponse:
    try:
        return await DecisionService().revoke(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            authorization_id=authorization_id,
            correlation_id=correlation_id(request),
        )
    except (DecisionConflict, DecisionNotFound) as exc:
        raise translate(exc) from exc
