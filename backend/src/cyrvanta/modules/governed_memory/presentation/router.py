from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from cyrvanta.modules.governed_memory.application.schemas import (
    FeedbackCreate,
    FeedbackList,
    FeedbackResponse,
    MemoryCandidateCreate,
    MemoryCandidateList,
    MemoryCandidateResponse,
    MemoryContextEvaluate,
    MemoryContextResponse,
    MemoryMetricList,
    MemoryReason,
    MemoryReviewCreate,
    MemoryVersionCreate,
)
from cyrvanta.modules.governed_memory.application.service import (
    GovernedMemoryConflict,
    GovernedMemoryNotFound,
    GovernedMemoryService,
)
from cyrvanta.shared.dependencies import SecurityContext, require_permission

router = APIRouter(tags=["governed-memory"])
FeedbackReader = Annotated[SecurityContext, Depends(require_permission("feedback.read"))]
FeedbackCreator = Annotated[SecurityContext, Depends(require_permission("feedback.create"))]
MemoryReader = Annotated[SecurityContext, Depends(require_permission("memory.read"))]
MemoryProposer = Annotated[SecurityContext, Depends(require_permission("memory.propose"))]
MemoryReviewer = Annotated[SecurityContext, Depends(require_permission("memory.review"))]
MemoryActivator = Annotated[SecurityContext, Depends(require_permission("memory.activate"))]
MemoryDisabler = Annotated[SecurityContext, Depends(require_permission("memory.disable"))]
MetricReader = Annotated[SecurityContext, Depends(require_permission("memory.metrics.read"))]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]


def correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


def translate(exc: Exception) -> HTTPException:
    if isinstance(exc, GovernedMemoryNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: FeedbackCreate,
    request: Request,
    context: FeedbackCreator,
    idempotency_key: IdempotencyKey,
) -> FeedbackResponse:
    try:
        return await GovernedMemoryService().create_feedback(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id(request),
        )
    except (GovernedMemoryConflict, GovernedMemoryNotFound, ValueError) as exc:
        raise translate(exc) from exc


@router.get("/feedback", response_model=FeedbackList)
async def list_feedback(
    context: FeedbackReader,
    resource_type: Literal["INCIDENT", "FINDING", "CLAIM", "ACTION_PROPOSAL", "PLAYBOOK_EXECUTION"]
    | None = None,
    resource_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> FeedbackList:
    return await GovernedMemoryService().list_feedback(
        context.tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/memory-candidates",
    response_model=MemoryCandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_candidate(
    payload: MemoryCandidateCreate,
    request: Request,
    context: MemoryProposer,
    idempotency_key: IdempotencyKey,
) -> MemoryCandidateResponse:
    try:
        return await GovernedMemoryService().create_candidate(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id(request),
        )
    except (GovernedMemoryConflict, GovernedMemoryNotFound, ValueError) as exc:
        raise translate(exc) from exc


@router.get("/memory-candidates", response_model=MemoryCandidateList)
async def list_candidates(
    context: MemoryReader,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> MemoryCandidateList:
    return await GovernedMemoryService().list_candidates(
        context.tenant_id, limit=limit, offset=offset
    )


@router.get("/memory-candidates/{candidate_id}", response_model=MemoryCandidateResponse)
async def get_candidate(candidate_id: UUID, context: MemoryReader) -> MemoryCandidateResponse:
    try:
        return await GovernedMemoryService().get_candidate(context.tenant_id, candidate_id)
    except GovernedMemoryNotFound as exc:
        raise translate(exc) from exc


@router.post(
    "/memory-candidates/{candidate_id}/versions",
    response_model=MemoryCandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    candidate_id: UUID,
    payload: MemoryVersionCreate,
    request: Request,
    context: MemoryProposer,
    idempotency_key: IdempotencyKey,
) -> MemoryCandidateResponse:
    """Correct a memory by writing a new version of it.

    Nothing is edited: the previous version keeps its text, its reviews and
    its history. Without this the review cycle had no exit -- asking for
    changes returned a candidate to draft where the only possible act was to
    submit the identical text again.
    """
    del idempotency_key
    try:
        return await GovernedMemoryService().create_version(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            candidate_id=candidate_id,
            payload=payload,
            correlation_id=correlation_id(request),
        )
    except (GovernedMemoryConflict, GovernedMemoryNotFound, ValueError) as exc:
        raise translate(exc) from exc


@router.post("/memory-versions/{version_id}/review-request", response_model=MemoryCandidateResponse)
async def request_review(
    version_id: UUID,
    payload: MemoryReason,
    request: Request,
    context: MemoryProposer,
    idempotency_key: IdempotencyKey,
) -> MemoryCandidateResponse:
    del idempotency_key
    try:
        return await GovernedMemoryService().request_review(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            version_id=version_id,
            payload=payload,
            correlation_id=correlation_id(request),
        )
    except (GovernedMemoryConflict, GovernedMemoryNotFound, ValueError) as exc:
        raise translate(exc) from exc


@router.post("/memory-versions/{version_id}/reviews", response_model=MemoryCandidateResponse)
async def review(
    version_id: UUID,
    payload: MemoryReviewCreate,
    request: Request,
    context: MemoryReviewer,
    idempotency_key: IdempotencyKey,
) -> MemoryCandidateResponse:
    del idempotency_key
    try:
        return await GovernedMemoryService().review(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            version_id=version_id,
            payload=payload,
            correlation_id=correlation_id(request),
        )
    except (GovernedMemoryConflict, GovernedMemoryNotFound, ValueError) as exc:
        raise translate(exc) from exc


@router.post("/memory-versions/{version_id}/activate", response_model=MemoryCandidateResponse)
async def activate(
    version_id: UUID,
    payload: MemoryReason,
    request: Request,
    context: MemoryActivator,
    idempotency_key: IdempotencyKey,
) -> MemoryCandidateResponse:
    del idempotency_key
    try:
        return await GovernedMemoryService().activate(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            version_id=version_id,
            payload=payload,
            correlation_id=correlation_id(request),
        )
    except (GovernedMemoryConflict, GovernedMemoryNotFound, ValueError) as exc:
        raise translate(exc) from exc


@router.post("/memory-versions/{version_id}/disable", response_model=MemoryCandidateResponse)
async def disable(
    version_id: UUID,
    payload: MemoryReason,
    request: Request,
    context: MemoryDisabler,
    idempotency_key: IdempotencyKey,
) -> MemoryCandidateResponse:
    del idempotency_key
    try:
        return await GovernedMemoryService().disable(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            version_id=version_id,
            payload=payload,
            correlation_id=correlation_id(request),
        )
    except (GovernedMemoryConflict, GovernedMemoryNotFound, ValueError) as exc:
        raise translate(exc) from exc


@router.get("/memory/active", response_model=MemoryCandidateList)
async def list_active(
    context: MemoryReader,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> MemoryCandidateList:
    return await GovernedMemoryService().list_active(context.tenant_id, limit=limit, offset=offset)


@router.post("/memory/context/evaluate", response_model=MemoryContextResponse)
async def evaluate_context(
    payload: MemoryContextEvaluate,
    request: Request,
    context: MemoryReader,
    idempotency_key: IdempotencyKey,
) -> MemoryContextResponse:
    return await GovernedMemoryService().evaluate_context(
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        payload=payload,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id(request),
    )


@router.get("/incidents/{incident_id}/memory-context", response_model=MemoryContextResponse)
async def incident_memory_context(
    incident_id: UUID,
    request: Request,
    context: MemoryReader,
) -> MemoryContextResponse:
    """Active memories that apply to this incident, as context to read.

    The facts it matches on are read from the incident here, not sent by the
    caller: a client that chooses its own facts chooses its own matches, and
    the fingerprint is meant to be evidence of what the case actually was.
    """
    try:
        return await GovernedMemoryService().incident_context(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            incident_id=incident_id,
            correlation_id=correlation_id(request),
        )
    except GovernedMemoryNotFound as exc:
        raise translate(exc) from exc


@router.get("/memory/metrics", response_model=MemoryMetricList)
async def list_metrics(
    context: MetricReader,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> MemoryMetricList:
    return await GovernedMemoryService().list_metrics(context.tenant_id, limit=limit, offset=offset)
