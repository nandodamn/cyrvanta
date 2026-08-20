from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from cyrvanta.modules.incident.application.schemas import (
    AlertResponse,
    AlertTriageUpdate,
    HistoryEntry,
    IncidentAlertsLink,
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
    ActionNotAllowed,
    AlertNotFound,
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
    granted_permissions,
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
    if isinstance(exc, IncidentNotFound | AlertNotFound):
        # An alert belonging to another tenant is reported as absent, not
        # refused: whether it exists is not this tenant's business.
        return HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    if isinstance(exc, ActionNotAllowed):
        # 403 with the reason: refused because of who the caller is to this
        # incident, not because the request was malformed.
        return HTTPException(status.HTTP_403_FORBIDDEN, exc.reason.value)
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
    # Resolving and closing are deliberately different authorities. Declaring
    # an incident technically resolved is the work of whoever handled it;
    # accepting that resolution and closing the case is someone else's
    # judgement. Both used to require incident.close, which collapsed the two.
    if payload.target_status == "resolved":
        permission = "incident.resolve"
    elif payload.target_status in {"closed", "reopened"}:
        permission = "incident.close"
    else:
        permission = "incident.update"
    await authorize(context, permission)
    try:
        incident = await service.transition(
            context.tenant_id,
            context.user_id,
            incident_id,
            payload,
            correlation_id(request),
            await granted_permissions(context),
        )
    except (IncidentNotFound, IncidentConflict, InvalidTransition, ActionNotAllowed) as exc:
        raise translate_error(exc) from exc
    return IncidentResponse.model_validate(incident)


@router.get("/incidents/{incident_id}/actions", response_model=list[str])
async def list_incident_actions(
    incident_id: UUID,
    context: IncidentRead,
    service: Service,
) -> list[str]:
    """Exactly what the caller may do to this incident, right now.

    The interface builds its menu from this instead of deciding for itself,
    which keeps one set of rules rather than two that drift apart.
    """
    try:
        return await service.available_actions(
            context.tenant_id,
            incident_id,
            context.user_id,
            await granted_permissions(context),
        )
    except IncidentNotFound as exc:
        raise translate_error(exc) from exc


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


@router.post("/incidents/{incident_id}/alerts", response_model=list[AlertResponse])
async def link_incident_alerts(
    incident_id: UUID,
    payload: IncidentAlertsLink,
    request: Request,
    context: IncidentUpdatePermission,
    service: Service,
) -> list[AlertResponse]:
    """Attach alerts to an incident as evidence.

    Guarded by incident.update rather than a permission of its own: changing
    what an incident is based on is changing the incident.
    """
    try:
        return await service.link_alerts(
            context.tenant_id,
            incident_id,
            context.user_id,
            payload,
            correlation_id(request),
        )
    except (IncidentNotFound, IncidentConflict, AlertNotFound) as exc:
        raise translate_error(exc) from exc


@router.get("/incidents/{incident_id}/history", response_model=list[HistoryEntry])
async def incident_history(
    incident_id: UUID,
    context: IncidentRead,
    service: Service,
) -> list[HistoryEntry]:
    """The incident's full record, audit and timeline merged chronologically.

    Read-only by construction: nothing in this module writes to either source
    except by recording a new event, so the record can be added to and never
    edited.
    """
    try:
        return await service.history(context.tenant_id, incident_id)
    except IncidentNotFound as exc:
        raise translate_error(exc) from exc


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
