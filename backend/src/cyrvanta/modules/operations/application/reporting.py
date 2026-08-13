from __future__ import annotations

import json
from html import escape
from uuid import UUID

from cyrvanta.modules.incident.application.service import IncidentService
from cyrvanta.modules.incident.infrastructure.models import IncidentModel
from cyrvanta.modules.operations.application.schemas import AnalysisResponse
from cyrvanta.modules.operations.application.service import OperationsService


class IncidentReportStateConflict(Exception):
    pass


class IncidentReportService:
    async def snapshot(
        self,
        tenant_id: UUID,
        incident_id: UUID,
        *,
        expected_version: int | None = None,
    ) -> dict[str, object]:
        incident = await IncidentService().get_incident(tenant_id, incident_id)
        if expected_version is not None and incident.version != expected_version:
            raise IncidentReportStateConflict("INCIDENT_VERSION_CONFLICT")
        analysis = await OperationsService().analyze(tenant_id, incident_id)
        return {
            "incident": {
                "id": str(incident.id),
                "code": incident.code,
                "title": incident.title,
                "status": incident.status,
                "severity": incident.severity,
                "priority": incident.priority,
                "classification": incident.classification,
                "version": incident.version,
                "detected_at": incident.detected_at.isoformat(),
            },
            "analysis": {
                "grounded": analysis.grounded,
                "mode": analysis.mode,
                "risk_score": analysis.risk_score,
                "summary_es": analysis.summary_es,
                "summary_en": analysis.summary_en,
                "techniques": [
                    {
                        "external_id": technique.external_id,
                        "name_es": technique.name_es,
                        "name_en": technique.name_en,
                        "tactic": technique.tactic,
                    }
                    for technique in analysis.techniques
                ],
                "recommendations": list(analysis.recommendations),
            },
        }

    async def egress_snapshot(
        self,
        tenant_id: UUID,
        incident_id: UUID,
        *,
        expected_version: int,
    ) -> dict[str, object]:
        incident = await IncidentService().get_incident(tenant_id, incident_id)
        if incident.version != expected_version:
            raise IncidentReportStateConflict("INCIDENT_VERSION_CONFLICT")
        analysis = await OperationsService().analyze(tenant_id, incident_id)
        incident = await IncidentService().get_incident(tenant_id, incident_id)
        if incident.version != expected_version:
            raise IncidentReportStateConflict("INCIDENT_VERSION_CONFLICT")
        return self.minimize_for_egress(incident, analysis)

    @staticmethod
    def minimize_for_egress(
        incident: IncidentModel, analysis: AnalysisResponse
    ) -> dict[str, object]:
        return {
            "incident": {
                "id": str(incident.id),
                "code": incident.code,
                "title": incident.title,
                "status": incident.status,
                "severity": incident.severity,
                "classification": incident.classification,
            },
            "risk": {"score": analysis.risk_score},
            "analysis": {
                "grounded": analysis.grounded,
                "mode": analysis.mode,
                "summary_es": analysis.summary_es,
                "summary_en": analysis.summary_en,
            },
        }

    @staticmethod
    def render_text(snapshot: dict[str, object]) -> str:
        return json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)

    @staticmethod
    def render_html(snapshot: dict[str, object]) -> str:
        incident = snapshot["incident"]
        analysis = snapshot["analysis"]
        if not isinstance(incident, dict) or not isinstance(analysis, dict):
            raise ValueError("invalid incident report snapshot")
        risk = snapshot.get("risk")
        risk_score = (
            risk.get("score", 0) if isinstance(risk, dict) else analysis.get("risk_score", 0)
        )
        techniques = analysis.get("techniques", [])
        technique_items = "".join(
            "<li>"
            + escape(str(item.get("external_id", "")))
            + " — "
            + escape(str(item.get("name_en", "")))
            + "</li>"
            for item in techniques
            if isinstance(item, dict)
        )
        techniques_html = (
            f"<h2>MITRE ATT&amp;CK</h2><ul>{technique_items}</ul>" if technique_items else ""
        )
        return (
            "<!doctype html><html><head><meta charset='utf-8'><title>Cyrvanta report</title>"
            "<style>body{font-family:sans-serif;max-width:900px;margin:40px}"
            "small{color:#555}</style></head><body>"
            f"<h1>{escape(str(incident.get('code', '')))}: "
            f"{escape(str(incident.get('title', '')))}</h1>"
            f"<p>Status: {escape(str(incident.get('status', '')))} · Severity: "
            f"{escape(str(incident.get('severity', '')))} · Risk: "
            f"{escape(str(risk_score))}/100</p>"
            f"<h2>Analysis</h2><p>{escape(str(analysis.get('summary_en', '')))}</p>"
            f"{techniques_html}"
            "<small>Generated by Cyrvanta. No raw telemetry or secrets included.</small>"
            "</body></html>"
        )
