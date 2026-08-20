from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from cyrvanta.modules.incident.application.schemas import (
    AlertResponse,
    AlertTriageUpdate,
    IncidentAssign,
    IncidentCreate,
    IncidentResponse,
    IncidentTransition,
    IncidentUpdate,
    Severity,
    TimelineCreate,
    TimelineResponse,
)
from cyrvanta.modules.incident.application.service import (
    AlertSort,
    IncidentConflict,
    IncidentNotFound,
    IncidentService,
    InvalidTransition,
)
from cyrvanta.shared.dependencies import (
    SecurityContext,
    authorize,
    get_security_context,
    require_permission,
)

router = APIRouter(tags=["incidents"])
Service = Annotated[IncidentService, Depends(IncidentService)]
Authenticated = Annotated[SecurityContext, Depends(get_security_context)]
AlertRead = Annotated[SecurityContext, Depends(require_permission("alert.read"))]
IncidentRead = Annotated[SecurityContext, Depends(require_permission("incident.read"))]
IncidentCreatePermission = Annotated[
    SecurityContext, Depends(require_permission("incident.create"))
]
IncidentUpdatePermission = Annotated[
    SecurityContext, Depends(require_permission("incident.update"))
]
IncidentAssignPermission = Annotated[
    SecurityContext, Depends(require_permission("incident.assign"))
]


def correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


def translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, IncidentNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    if isinstance(exc, IncidentConflict):
        return HTTPException(status.HTTP_409_CONFLICT, "Incident version conflict")
    return HTTPException(status.HTTP_409_CONFLICT, "Invalid incident transition")


@router.get("/alerts", response_model=list[AlertResponse])
async def list_alerts(
    context: AlertRead,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: Annotated[AlertSort, Query()] = "recent",
    severity: Annotated[list[Severity] | None, Query()] = None,
) -> list[AlertResponse]:
    return [
        AlertResponse.model_validate(item)
        for item in await service.list_alerts(context.tenant_id, limit, offset, q, sort, severity)
    ]


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: UUID, context: AlertRead, service: Service) -> AlertResponse:
    try:
        return AlertResponse.model_validate(await service.get_alert(context.tenant_id, alert_id))
    except IncidentNotFound as exc:
        raise translate_error(exc) from exc


@router.post("/alerts/{alert_id}/triage", response_model=AlertResponse)
async def triage_alert(
    alert_id: UUID,
    payload: AlertTriageUpdate,
    request: Request,
    context: AlertRead,
    service: Service,
) -> AlertResponse:
    try:
        return await service.triage_alert(
            context.tenant_id,
            context.user_id,
            alert_id,
            payload,
            correlation_id(request),
        )
    except IncidentNotFound as exc:
        raise translate_error(exc) from exc


@router.get("/incidents", response_model=list[IncidentResponse])
async def list_incidents(
    context: IncidentRead,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[IncidentResponse]:
    return [
        IncidentResponse.model_validate(item)
        for item in await service.list_incidents(context.tenant_id, limit, offset, q)
    ]


@router.post("/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreate,
    request: Request,
    context: IncidentCreatePermission,
    service: Service,
) -> IncidentResponse:
    incident = await service.create_incident(
        context.tenant_id, context.user_id, payload, correlation_id(request)
    )
    return IncidentResponse.model_validate(incident)


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: UUID, context: IncidentRead, service: Service
) -> IncidentResponse:
    try:
        return IncidentResponse.model_validate(
            await service.get_incident(context.tenant_id, incident_id)
        )
    except IncidentNotFound as exc:
        raise translate_error(exc) from exc


@router.get("/incidents/{incident_id}/alerts", response_model=list[AlertResponse])
async def list_incident_alerts(
    incident_id: UUID, context: AlertRead, service: Service
) -> list[AlertResponse]:
    try:
        return await service.list_incident_alerts(context.tenant_id, incident_id)
    except IncidentNotFound as exc:
        raise translate_error(exc) from exc


@router.patch("/incidents/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: UUID,
    payload: IncidentUpdate,
    request: Request,
    context: IncidentUpdatePermission,
    service: Service,
) -> IncidentResponse:
    try:
        incident = await service.update_incident(
            context.tenant_id,
            context.user_id,
            incident_id,
            payload,
            correlation_id(request),
        )
    except (IncidentNotFound, IncidentConflict) as exc:
        raise translate_error(exc) from exc
    return IncidentResponse.model_validate(incident)


@router.post("/incidents/{incident_id}/transition", response_model=IncidentResponse)
async def transition_incident(
    incident_id: UUID,
    payload: IncidentTransition,
    request: Request,
    context: Authenticated,
    service: Service,
) -> IncidentResponse:
    permission = (
        "incident.close"
        if payload.target_status in {"resolved", "closed", "reopened"}
        else "incident.update"
    )
    await authorize(context, permission)
    try:
        incident = await service.transition(
            context.tenant_id,
            context.user_id,
            incident_id,
            payload,
            correlation_id(request),
        )
    except (IncidentNotFound, IncidentConflict, InvalidTransition) as exc:
        raise translate_error(exc) from exc
    return IncidentResponse.model_validate(incident)


@router.post("/incidents/{incident_id}/assign", response_model=IncidentResponse)
async def assign_incident(
    incident_id: UUID,
    payload: IncidentAssign,
    request: Request,
    context: IncidentAssignPermission,
    service: Service,
) -> IncidentResponse:
    try:
        incident = await service.assign(
            context.tenant_id,
            context.user_id,
            incident_id,
            payload,
            correlation_id(request),
        )
    except (IncidentNotFound, IncidentConflict) as exc:
        raise translate_error(exc) from exc
    return IncidentResponse.model_validate(incident)


@router.get("/incidents/{incident_id}/timeline", response_model=list[TimelineResponse])
async def list_timeline(
    incident_id: UUID, context: IncidentRead, service: Service
) -> list[TimelineResponse]:
    try:
        return [
            TimelineResponse.model_validate(item)
            for item in await service.list_timeline(context.tenant_id, incident_id)
        ]
    except IncidentNotFound as exc:
        raise translate_error(exc) from exc


@router.post(
    "/incidents/{incident_id}/timeline",
    response_model=TimelineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_timeline(
    incident_id: UUID,
    payload: TimelineCreate,
    request: Request,
    context: IncidentUpdatePermission,
    service: Service,
) -> TimelineResponse:
    try:
        entry = await service.add_timeline(
            context.tenant_id,
            context.user_id,
            incident_id,
            payload,
            correlation_id(request),
        )
    except (IncidentNotFound, IncidentConflict) as exc:
        raise translate_error(exc) from exc
    return TimelineResponse.model_validate(entry)
