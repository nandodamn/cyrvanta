from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from cyrvanta.modules.integrations.infrastructure.composition import (
    configured_wazuh_connector,
)
from cyrvanta.modules.integrations.application.connection_service import (
    IntegrationConfigurationError,
    IntegrationConfigurationWrite,
    IntegrationConnectionResponse,
    IntegrationConnectionService,
    IntegrationProbeResponse,
)
from cyrvanta.modules.operations.application.activity import (
    OperationalActivity24h,
    OperationalActivityService,
)
from cyrvanta.modules.operations.application.schemas import (
    AnalysisResponse,
    IntegrationHealth,
    NetworkTopologyResponse,
    PlaybookCatalogResponse,
    PlaybookManagementResponse,
    Technique,
)
from cyrvanta.modules.operations.application.reporting import IncidentReportService
from cyrvanta.modules.operations.application.service import OperationsService
from cyrvanta.modules.operations.application.topology_service import NetworkTopologyService
from cyrvanta.modules.operations.infrastructure.n8n_catalog import N8nWorkflowCatalog
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.dependencies import SecurityContext, authorize, require_permission

router = APIRouter(tags=["operations"])
IncidentReader = Annotated[SecurityContext, Depends(require_permission("incident.read"))]
AnalysisRequester = Annotated[SecurityContext, Depends(require_permission("analysis.request"))]
PlaybookReader = Annotated[SecurityContext, Depends(require_permission("playbook.read"))]
PlaybookManager = Annotated[SecurityContext, Depends(require_permission("playbook.manage"))]
IntegrationReader = Annotated[SecurityContext, Depends(require_permission("integration.read"))]
IntegrationManager = Annotated[SecurityContext, Depends(require_permission("integration.manage"))]


def correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


@router.get("/integrations/health", response_model=list[IntegrationHealth])
async def integration_health(context: IntegrationReader) -> list[IntegrationHealth]:
    return await OperationsService(configured_wazuh_connector(context.tenant_id)).health()


@router.get("/integrations/connections/resolve")
async def resolve_connection(
    context: IntegrationReader,
    capability: Annotated[str, Query(max_length=120)],
    environment: Annotated[str, Query(max_length=40)] = "live",
) -> dict[str, object]:
    from cyrvanta.modules.integrations.application.resolver import ConnectionResolver

    result = await ConnectionResolver().resolve(
        tenant_id=context.tenant_id,
        required_capability=capability,
        environment=environment,
    )
    return {
        "resolution_status": result.resolution_status,
        "connection_id": result.connection_id,
        "connector_type": result.connector_type,
        "capability": result.capability,
        "selection_reason": result.selection_reason,
        "requires_approval": result.requires_approval,
        "simulation_supported": result.simulation_supported,
        "verification_supported": result.verification_supported,
        "blocking": result.blocking,
    }


@router.get("/integrations/connections", response_model=list[IntegrationConnectionResponse])
async def list_connections(context: IntegrationReader) -> list[IntegrationConnectionResponse]:
    return await IntegrationConnectionService().list(context.tenant_id)


@router.post("/integrations/connections/{connection_id}/test", response_model=IntegrationProbeResponse)
async def test_connection(
    connection_id: UUID,
    context: IntegrationManager,
    request: Request,
) -> IntegrationProbeResponse:
    try:
        return await IntegrationConnectionService().probe(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            connection_id=connection_id,
            correlation_id=correlation_id(request),
        )
    except IntegrationConfigurationError as exc:
        code = str(exc)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND if code == "INTEGRATION_NOT_FOUND" else status.HTTP_409_CONFLICT,
            code,
        ) from exc


@router.post("/integrations/connections/{connection_id}/configure", response_model=IntegrationConnectionResponse)
async def configure_connection(
    connection_id: str,
    payload: IntegrationConfigurationWrite,
    context: IntegrationManager,
    request: Request,
) -> IntegrationConnectionResponse:
    try:
        return await IntegrationConnectionService().configure(
            tenant_id=context.tenant_id,
            actor_user_id=context.user_id,
            connection_id=connection_id,
            payload=payload,
            correlation_id=correlation_id(request),
        )
    except IntegrationConfigurationError as exc:
        code = str(exc)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND if code == "INTEGRATION_NOT_FOUND" else status.HTTP_409_CONFLICT,
            code,
        ) from exc

@router.get("/operations/activity-24h", response_model=OperationalActivity24h)
async def operational_activity_24h(context: IncidentReader) -> OperationalActivity24h:
    await authorize(context, "alert.read")
    return await OperationalActivityService().get(context.tenant_id)


@router.get("/operations/topology", response_model=NetworkTopologyResponse)
async def network_topology(context: IncidentReader) -> NetworkTopologyResponse:
    await authorize(context, "alert.read")
    return await NetworkTopologyService().get_topology(context.tenant_id)


@router.get("/mitre/techniques", response_model=list[Technique])
async def techniques(context: IncidentReader) -> list[Technique]:
    return OperationsService.techniques()


@router.get("/playbooks", response_model=PlaybookCatalogResponse)
async def playbooks(
    context: PlaybookReader,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> PlaybookCatalogResponse:
    settings = get_settings()
    service = OperationsService(
        workflow_catalog=N8nWorkflowCatalog(settings),
    )
    return await service.playbooks(limit, offset, q)


@router.get("/playbooks/management", response_model=PlaybookManagementResponse)
async def playbook_management(context: PlaybookManager) -> PlaybookManagementResponse:
    settings = get_settings()
    return PlaybookManagementResponse(
        editor_url=settings.n8n_editor_url,
        local_only=True,
        api_sync_configured=bool(settings.n8n_api_key),
    )


@router.post("/incidents/{incident_id}/analysis", response_model=AnalysisResponse)
async def analyze(
    incident_id: UUID, request: Request, context: AnalysisRequester
) -> AnalysisResponse:
    service = OperationsService()
    result = await service.analyze(
        context.tenant_id,
        incident_id,
        correlation_id=correlation_id(request),
        record_claims=True,
    )
    await service.audit(
        context.tenant_id,
        context.user_id,
        correlation_id(request),
        "analysis.requested",
        "incident",
        incident_id,
        {"provider": result.provider, "mode": result.mode, "risk_score": result.risk_score},
    )
    return result


@router.get("/incidents/{incident_id}/report")
async def report(incident_id: UUID, request: Request, context: IncidentReader) -> Response:
    snapshot = await IncidentReportService().snapshot(context.tenant_id, incident_id)
    incident = snapshot["incident"]
    if not isinstance(incident, dict):
        raise RuntimeError("invalid incident report snapshot")
    body = IncidentReportService.render_html(snapshot)
    await OperationsService().audit(
        context.tenant_id,
        context.user_id,
        correlation_id(request),
        "report.generated",
        "incident",
        incident_id,
        {"format": "html", "provenance": "live"},
    )
    filename = str(incident.get("code", "incident"))
    return Response(
        body,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}.html"'},
    )
