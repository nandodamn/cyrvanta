from html import escape
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from cyrvanta.modules.incident.application.service import IncidentService
from cyrvanta.modules.integrations.infrastructure.composition import (
    configured_wazuh_connector,
)
from cyrvanta.modules.operations.application.schemas import (
    AnalysisResponse,
    AutomationRequest,
    AutomationResponse,
    IntegrationHealth,
    PlaybookCatalogResponse,
    PlaybookManagementResponse,
    Technique,
)
from cyrvanta.modules.operations.application.service import OperationsService
from cyrvanta.modules.operations.infrastructure.n8n_catalog import N8nWorkflowCatalog
from cyrvanta.shared.config import get_settings
from cyrvanta.shared.dependencies import SecurityContext, require_permission

router = APIRouter(tags=["operations"])
IncidentReader = Annotated[SecurityContext, Depends(require_permission("incident.read"))]
AnalysisRequester = Annotated[
    SecurityContext, Depends(require_permission("analysis.request"))
]
ResponseExecutor = Annotated[
    SecurityContext, Depends(require_permission("response.execute"))
]
PlaybookReader = Annotated[
    SecurityContext, Depends(require_permission("playbook.read"))
]
PlaybookManager = Annotated[
    SecurityContext, Depends(require_permission("playbook.manage"))
]


def correlation_id(request: Request) -> UUID:
    return UUID(request.state.correlation_id)


@router.get("/integrations/health", response_model=list[IntegrationHealth])
async def integration_health(context: IncidentReader) -> list[IntegrationHealth]:
    return await OperationsService(configured_wazuh_connector(context.tenant_id)).health()


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
        context.tenant_id, context.user_id, correlation_id(request),
        "analysis.requested", "incident", incident_id,
        {"provider": result.provider, "mode": result.mode, "risk_score": result.risk_score},
    )
    return result


@router.post("/automations/execute", response_model=AutomationResponse)
async def execute(
    payload: AutomationRequest, request: Request, context: ResponseExecutor
) -> AutomationResponse:
    await IncidentService().get_incident(context.tenant_id, payload.incident_id)
    service = OperationsService()
    try:
        result = await service.execute(payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await service.audit(
        context.tenant_id, context.user_id, correlation_id(request),
        "response.execution.requested", "incident", payload.incident_id,
        {"workflow_id": result.workflow_id, "mode": result.mode, "status": result.status},
    )
    return result


@router.get("/incidents/{incident_id}/report")
async def report(incident_id: UUID, request: Request, context: IncidentReader) -> Response:
    incident = await IncidentService().get_incident(context.tenant_id, incident_id)
    analysis = await OperationsService().analyze(context.tenant_id, incident_id)
    provenance = "SIMULATED" if incident.is_simulated else "LIVE"
    body = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Cyrvanta report</title>"
        "<style>body{font-family:sans-serif;max-width:900px;margin:40px}small{color:#555}</style>"
        f"</head><body><h1>{escape(incident.code)}: {escape(incident.title)}</h1>"
        f"<p><strong>{provenance}</strong> · tenant {context.tenant_id}</p>"
        f"<p>Status: {escape(incident.status)} · Severity: {escape(incident.severity)} · Risk: "
        f"{analysis.risk_score}/100</p><h2>Analysis</h2><p>{escape(analysis.summary_en)}</p>"
        "<h2>MITRE ATT&CK</h2><ul>"
        + "".join(
            f"<li>{escape(item.external_id)} — {escape(item.name_en)}</li>"
            for item in analysis.techniques
        )
        + "</ul><small>Generated by Cyrvanta. No raw telemetry or secrets included.</small>"
        "</body></html>"
    )
    await OperationsService().audit(
        context.tenant_id, context.user_id, correlation_id(request),
        "report.generated", "incident", incident_id,
        {"format": "html", "provenance": provenance.lower()},
    )
    return Response(body, media_type="text/html",
                    headers={"Content-Disposition": f'attachment; filename="{incident.code}.html"'})
