import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx

from cyrvanta.modules.claims.application.service import (
    AnalysisClaimInput,
    ClaimService,
)
from cyrvanta.modules.claims.domain.models import ClaimType
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
from cyrvanta.modules.incident.application.service import IncidentService
from cyrvanta.modules.integrations.application.ports.siem_connector import (
    SIEMConnectorPort,
)
from cyrvanta.modules.integrations.domain.findings import (
    EffectiveTimeBasis,
    FingerprintMode,
    NormalizationAssessment,
    NormalizationStatus,
)
from cyrvanta.modules.integrations.domain.models import (
    CanonicalFinding,
    ConnectorStatus,
    ExternalEvidenceReference,
)
from cyrvanta.modules.operations.application.ports import (
    WorkflowCatalogPort,
    WorkflowSnapshot,
)
from cyrvanta.modules.operations.application.schemas import (
    AnalysisResponse,
    IntegrationHealth,
    PlaybookCatalogResponse,
    PlaybookConnector,
    PlaybookSummary,
    Technique,
)
from cyrvanta.modules.threat_knowledge.application.service import (
    EnrichmentUnavailable,
    ThreatEnrichmentService,
)
from cyrvanta.shared.config import Settings, get_settings
from cyrvanta.shared.database import tenant_session
from cyrvanta.shared.infrastructure.event_store import SqlEventStore

CATALOG = {
    "T1110": Technique(
        external_id="T1110",
        name_es="Fuerza bruta",
        name_en="Brute Force",
        tactic="credential-access",
    ),
    "T1078": Technique(
        external_id="T1078",
        name_es="Cuentas válidas",
        name_en="Valid Accounts",
        tactic="defense-evasion",
    ),
    "T1098": Technique(
        external_id="T1098",
        name_es="Manipulación de cuenta",
        name_en="Account Manipulation",
        tactic="persistence",
    ),
}

PLAYBOOK_METADATA = {
    "block-ip-address": ("Cyrvanta — Block IP Address", ("firewall-gateway",)),
    "isolate-endpoint": ("Cyrvanta — Isolate Host Endpoint", ("edr-agent",)),
    "revoke-user-sessions": ("Cyrvanta — Revoke Active User Sessions", ("identity-provider",)),
    "cyrvanta-notify-critical-incident": (
        "Cyrvanta — Notify Critical Incident",
        ("notification-channel",),
    ),
    "cyrvanta-create-security-ticket": (
        "Cyrvanta — Create Security Ticket",
        ("ticketing-system",),
    ),
    "cyrvanta-request-dual-approval": (
        "Cyrvanta — Request Dual Approval",
        ("notification-channel",),
    ),
    "cyrvanta-incident-report-email": (
        "Cyrvanta — Incident Report Email",
        ("smtp-outbound",),
    ),
}


class OperationsService:
    def __init__(
        self,
        siem_connector: SIEMConnectorPort | None = None,
        workflow_catalog: WorkflowCatalogPort | None = None,
    ) -> None:
        self.settings: Settings = get_settings()
        self.siem_connector = siem_connector
        self.workflow_catalog = workflow_catalog

    async def health(self) -> list[IntegrationHealth]:
        return [
            await self._http_health(
                "opensearch", self.settings.opensearch_mode, self.settings.opensearch_url
            ),
            await self._siem_health(),
            await self._http_health(
                "ollama", self.settings.ollama_mode, f"{self.settings.ollama_base_url}/api/tags"
            ),
            await self._http_health(
                "n8n", self.settings.n8n_mode, f"{self.settings.n8n_base_url}/healthz"
            ),
        ]

    async def _http_health(self, code: str, mode: str, url: str) -> IntegrationHealth:
        normalized = self._mode(mode)
        if normalized == "disabled":
            return IntegrationHealth(code=code, mode=normalized, healthy=False, detail="disabled")
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(url)
            return IntegrationHealth(
                code=code,
                mode=normalized,
                healthy=response.is_success,
                detail=f"HTTP {response.status_code}",
            )
        except httpx.HTTPError:
            return IntegrationHealth(
                code=code, mode=normalized, healthy=False, detail="unavailable"
            )

    async def _siem_health(self) -> IntegrationHealth:
        normalized = self._mode(self.settings.wazuh_mode)
        if normalized == "disabled":
            return IntegrationHealth(
                code="wazuh", mode=normalized, healthy=False, detail="disabled"
            )
        if self.siem_connector is None:
            return IntegrationHealth(
                code="wazuh", mode=normalized, healthy=False, detail="unavailable"
            )
        health = await self.siem_connector.health_check()
        return IntegrationHealth(
            code="wazuh",
            mode=normalized,
            healthy=health.status == ConnectorStatus.HEALTHY,
            detail=health.detail or health.status.value,
        )

    async def playbooks(
        self, limit: int, offset: int, query: str | None
    ) -> PlaybookCatalogResponse:
        allowed = self.settings.allowed_workflow_ids
        synchronized = False
        sync_detail = "api_key_not_configured"
        discovered: tuple[WorkflowSnapshot, ...] = ()
        if self.workflow_catalog is not None:
            snapshot = await self.workflow_catalog.list_workflows()
            synchronized = snapshot.synchronized
            sync_detail = snapshot.detail
            discovered = snapshot.workflows

        by_id: dict[str, WorkflowSnapshot] = {
            workflow.workflow_id: workflow for workflow in discovered
        }
        items: list[PlaybookSummary] = []
        for workflow_id in sorted(allowed):
            workflow = by_id.get(workflow_id)
            connectors = (
                [
                    PlaybookConnector(
                        node_type=node.node_type,
                        name=node.name,
                        credential_names=list(node.credential_names),
                    )
                    for node in workflow.nodes
                ]
                if workflow is not None
                else [
                    PlaybookConnector(
                        node_type="credential-alias",
                        name=alias,
                        credential_names=[],
                    )
                    for alias in PLAYBOOK_METADATA.get(workflow_id, (workflow_id, ()))[1]
                ]
            )
            items.append(
                PlaybookSummary(
                    workflow_id=workflow_id,
                    name=(
                        workflow.name
                        if workflow is not None
                        else self._fallback_playbook_name(workflow_id)
                    ),
                    active=workflow.active if workflow is not None else None,
                    registered=True,
                    version_id=workflow.version_id if workflow is not None else None,
                    connectors=connectors,
                )
            )

        normalized_query = (query or "").strip().casefold()
        if normalized_query:
            items = [
                item
                for item in items
                if normalized_query in item.workflow_id.casefold()
                or normalized_query in item.name.casefold()
                or any(
                    normalized_query in connector.name.casefold()
                    or normalized_query in connector.node_type.casefold()
                    for connector in item.connectors
                )
            ]
        return PlaybookCatalogResponse(
            items=items[offset : offset + limit],
            total=len(items),
            synchronized=synchronized,
            sync_detail=sync_detail,
            mode=self._mode(self.settings.n8n_mode),
        )

    @staticmethod
    def _fallback_playbook_name(workflow_id: str) -> str:
        return PLAYBOOK_METADATA.get(workflow_id, (workflow_id, ()))[0]

    async def analyze(
        self,
        tenant_id: UUID,
        incident_id: UUID,
        *,
        correlation_id: UUID | None = None,
        record_claims: bool = False,
    ) -> AnalysisResponse:
        incident = await IncidentService().get_incident(tenant_id, incident_id)
        normalized_finding = self._incident_as_canonical_finding(
            tenant_id=tenant_id,
            incident_id=incident.id,
            occurred_at=incident.detected_at,
            title=incident.title,
            description=incident.description,
            severity=incident.severity,
            category=incident.classification,
            status=incident.status,
        )
        techniques: list[Technique] = []
        confidence = 0.0
        risk = 0
        summary_es = (
            "Evidencia insuficiente: el incidente todav\u00eda no tiene un "
            "an\u00e1lisis de riesgo persistido."
        )
        summary_en = (
            "Insufficient evidence: the incident does not yet have a persisted risk analysis."
        )
        provider = "none"
        model = "not-applicable"
        mode = "evidence-unavailable"
        grounded = False
        async with tenant_session(tenant_id) as session:
            events = SqlEventStore(
                session_factory=None,  # type: ignore[arg-type]
                max_payload_bytes=self.settings.event_max_payload_bytes,
            ).recorder(session)
            try:
                enrichment = await ThreatEnrichmentService(session, events).get(
                    tenant_id, incident_id
                )
            except EnrichmentUnavailable:
                enrichment = None
        if enrichment is not None:
            risk = enrichment.risk.score
            by_locale = {(item.locale, item.mode): item for item in enrichment.explanations}
            selected_mode = next(
                (
                    candidate
                    for candidate in ("AI_REDACTION", "DETERMINISTIC")
                    if ("es", candidate) in by_locale
                    and ("en", candidate) in by_locale
                    and by_locale[("es", candidate)].grounded
                    and by_locale[("en", candidate)].grounded
                ),
                None,
            )
            if selected_mode is not None:
                summary_es = by_locale[("es", selected_mode)].text
                summary_en = by_locale[("en", selected_mode)].text
                provider = by_locale[("en", selected_mode)].provider
                model = (
                    self.settings.ollama_model
                    if selected_mode == "AI_REDACTION"
                    else "not-applicable"
                )
                mode = selected_mode.casefold()
                grounded = True
            techniques = [
                Technique(
                    external_id=item.external_id,
                    name_es=(
                        CATALOG[item.external_id].name_es
                        if item.external_id in CATALOG
                        else item.name_en
                    ),
                    name_en=item.name_en,
                    tactic=item.tactic_codes[0] if item.tactic_codes else "unknown",
                )
                for item in enrichment.mappings
                if item.status in {"SUPPORTED", "VALIDATED"}
            ]
        result = AnalysisResponse(
            incident_id=incident.id,
            provider=provider,
            model=model,
            mode=mode,
            summary_es=summary_es,
            summary_en=summary_en,
            confidence=confidence,
            risk_score=risk,
            techniques=techniques,
            recommendations=[],
            grounded=grounded,
        )
        if record_claims and result.grounded:
            if correlation_id is None:
                raise ValueError("correlation_id is required when recording claims")
            claim_inputs = (
                AnalysisClaimInput(
                    claim_type=ClaimType.INFERENCE,
                    statement=summary_en,
                    language_code="en",
                    confidence=confidence,
                    explanation=(
                        "Evidence-bounded incident analysis; this inference is not a verified fact."
                    ),
                    presentation_locale="es",
                    presentation_text=summary_es,
                    claim_slot="summary",
                ),
                *(
                    AnalysisClaimInput(
                        claim_type=ClaimType.INFERENCE,
                        statement=(
                            f"MITRE ATT&CK technique {technique.external_id} "
                            f"({technique.name_en}) may apply to this incident."
                        ),
                        language_code="en",
                        confidence=confidence,
                        explanation=(
                            "Proposed technique mapping derived from the current incident context."
                        ),
                        presentation_locale="es",
                        presentation_text=(
                            f"La técnica MITRE ATT&CK {technique.external_id} "
                            f"({technique.name_es}) podría aplicar a este incidente."
                        ),
                    )
                    for technique in techniques
                ),
                *(
                    AnalysisClaimInput(
                        claim_type=ClaimType.RECOMMENDATION,
                        statement=recommendation,
                        language_code="es",
                        confidence=confidence,
                        explanation=(
                            "Proposed investigative or response step; it is not an authorization."
                        ),
                    )
                    for recommendation in result.recommendations
                ),
            )
            await ClaimService().record_analysis(
                tenant_id=tenant_id,
                incident_id=incident_id,
                correlation_id=correlation_id,
                provider=provider,
                model=model,
                mode=mode,
                input_fingerprint=normalized_finding.payload_fingerprint,
                claims=claim_inputs,
            )
        return result

    @staticmethod
    def _incident_as_canonical_finding(
        tenant_id: UUID,
        incident_id: UUID,
        occurred_at: datetime,
        title: str,
        description: str,
        severity: str,
        category: str,
        status: str,
    ) -> CanonicalFinding:
        severity_score = {
            "informational": 10,
            "low": 25,
            "medium": 45,
            "high": 70,
            "critical": 90,
        }.get(severity, 25)
        source_instance_id = uuid5(NAMESPACE_URL, f"cyrvanta:{tenant_id}:core")
        payload_hash = sha256(
            json.dumps(
                {
                    "incident_id": str(incident_id),
                    "occurred_at": occurred_at.astimezone(UTC).isoformat(),
                    "title": title,
                    "description": description,
                    "severity": severity,
                    "category": category,
                    "status": status,
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return CanonicalFinding(
            finding_id=incident_id,
            tenant_id=tenant_id,
            integration_id=source_instance_id,
            source_system="cyrvanta",
            source_instance_id=source_instance_id,
            source_object_type="incident",
            source_object_id=str(incident_id),
            source_occurred_at=occurred_at,
            observed_at=datetime.now(UTC),
            effective_at=occurred_at,
            effective_time_basis=EffectiveTimeBasis.SOURCE,
            title=title,
            description=description,
            severity_score=severity_score,
            category=category,
            status=status,
            evidence_reference=ExternalEvidenceReference(
                source_system="cyrvanta",
                source_instance_id=source_instance_id,
                source_object_type="incident",
                source_object_id=str(incident_id),
                source_timestamp=occurred_at,
                locator=f"cyrvanta://incidents/{incident_id}",
                adapter_version="core-1",
                normalizer_version="canonical-1",
                payload_sha256=payload_hash,
            ),
            payload_fingerprint=payload_hash,
            normalization=NormalizationAssessment(
                status=NormalizationStatus.VALID,
                completeness_score=100,
                issue_codes=(),
                adapter_name="cyrvanta",
                adapter_version="core-1",
                normalizer_version="canonical-1",
                fingerprint_mode=FingerprintMode.ADAPTER_MATERIAL,
            ),
        )

    async def audit(
        self,
        tenant_id: UUID,
        actor_id: UUID,
        correlation_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID,
        details: dict[str, object],
    ) -> None:
        async with tenant_session(tenant_id) as session:
            session.add(
                AuditEventModel(
                    tenant_id=tenant_id,
                    actor_user_id=actor_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    outcome="success",
                    correlation_id=correlation_id,
                    details=details,
                )
            )

    @staticmethod
    def techniques() -> list[Technique]:
        return list(CATALOG.values())

    @staticmethod
    def _mode(value: str) -> Literal["disabled", "live"]:
        if value not in {"disabled", "live"}:
            return "disabled"
        return value  # type: ignore[return-value]
