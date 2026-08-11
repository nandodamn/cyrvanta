from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
from cyrvanta.modules.playbooks.application.administration_schemas import (
    ActionList,
    ActionResponse,
    BindingCreate,
    BindingList,
    BindingResponse,
    DefinitionCreate,
    DefinitionList,
    DefinitionResponse,
    DryRunResponse,
    NativeActionBindingCreate,
    NativeActionBindingResponse,
    ToggleBindingPayload,
    UpdateApprovalGovernancePayload,
    VersionCreate,
    VersionResponse,
)

PLAYBOOK_INCIDENT_TYPES: dict[str, list[str]] = {
    "simulate-user-block": ["credential-access", "unauthorized-access"],
    "notify-critical-incident": ["critical-incidents", "high-risk-detection"],
    "create-security-ticket": ["operational-tracking", "all-incidents"],
    "request-dual-approval": ["high-impact-containment", "destructive-actions"],
    "incident-report-email": ["incident-reporting", "stakeholder-briefing"],
}

PLAYBOOK_MITRE_CODES: dict[str, list[str]] = {
    "simulate-user-block": ["T1110", "T1078", "T1098"],
    "notify-critical-incident": ["T1078", "T1110", "T1499"],
    "create-security-ticket": ["T1059", "T1078"],
    "request-dual-approval": ["T1098", "T1485"],
    "incident-report-email": ["T1078", "T1110"],
}

PLAYBOOK_AUTOMATION_POLICY_MAP: dict[str, dict[str, str]] = {
    "compromised-account": {
        "es": "Revocar sesiones: automática (riesgo medio/alto). Bloqueo de cuenta común: con aprobación. Bloqueo de cuenta privilegiada: aprobación obligatoria.",
        "en": "Revoke sessions: automatic (medium/high risk). Standard account block: approval-based. Privileged account block: mandatory approval.",
    },
    "compromised-endpoint": {
        "es": "Recolección de evidencia e IoCs: automática. Cuarentena de archivos: automática (confianza alta). Aislamiento de host: automático en estaciones, aprobación en servidores.",
        "en": "Evidence and IoC collection: automatic. File quarantine: automatic (high confidence). Host isolation: automatic for workstations, approval for servers.",
    },
    "phishing-malicious-email": {
        "es": "Enriquecimiento y búsqueda: automática. Eliminación masiva de correo: aprobación humana obligatoria. Bloqueo de dominio: automático con tiempo acotado.",
        "en": "Enrichment & search: automatic. Mass email deletion: mandatory human approval. Domain blocking: automatic with time limit.",
    },
    "ransomware-destructive": {
        "es": "Enriquecimiento y alerta crítica: automática. Aislamiento de estaciones: automático con evidencia fuerte. Servidores críticos y backups: aprobación explícita.",
        "en": "Enrichment & critical alert: automatic. Station isolation: automatic with strong evidence. Critical servers and backups: explicit approval.",
    },
    "lateral-movement": {
        "es": "Correlación y revocación de sesiones: automática. Bloqueo de conexiones laterales y aislamiento de host: aprobación previa.",
        "en": "Correlation and session revocation: automatic. Lateral connection block and host isolation: prior approval required.",
    },
    "malicious-indicator": {
        "es": "Búsqueda y enriquecimiento: automático. Bloqueo temporal: automático con alta confianza. Bloqueo permanente: aprobación humana.",
        "en": "Search and enrichment: automatic. Temporary block: automatic with high confidence. Permanent block: human approval.",
    },
    "privilege-escalation": {
        "es": "Contraste con tickets de cambio: automático. Reversión de privilegios y suspensión de cuenta administrada: aprobación obligatoria.",
        "en": "Contrast with change tickets: automatic. Privilege reversal and admin account suspension: mandatory approval.",
    },
    "security-control-disabled": {
        "es": "Restauración de control EDR/Logs: automática. Suspensión preventiva del sistema: aprobación según severidad.",
        "en": "EDR/Logs control restoration: automatic. Preventive system suspension: approval according to severity.",
    },
    "automated-enrichment": {
        "es": "Totalmente automática (sin mutación de estado). Prepara el contexto para la decisión humana.",
        "en": "Fully automatic (non-mutating). Prepares context for human decision.",
    },
    "escalation-notification": {
        "es": "Automática según SLAs del tenant y matriz de severidad del incidente.",
        "en": "Automatic based on tenant SLAs and incident severity matrix.",
    },
    "evidence-preservation": {
        "es": "Automática al crearse incidentes de alta/crítica severidad. Almacén inmutable cifrado.",
        "en": "Automatic upon high/critical incident creation. Immutable encrypted vault.",
    },
    "closure-controlled-learning": {
        "es": "Verificación de contención automática. Integración de aprendizaje a la memoria gobernada: aprobación humana obligatoria.",
        "en": "Automatic containment verification. Memory candidate learning integration: mandatory human approval.",
    },
}

PLAYBOOK_ROLLBACK_MAP: dict[str, dict[str, str]] = {
    "compromised-account": {
        "code": "rollback-compromised-account",
        "es": "Restauración de cuenta y desbloqueo de sesiones.",
        "en": "Account restoration and session unblock.",
    },
    "compromised-endpoint": {
        "code": "rollback-compromised-endpoint",
        "es": "Liberación de aislamiento de host y restauración de cuarentena.",
        "en": "Host isolation release and quarantine restoration.",
    },
}

ESSENTIAL_NATIVE_PLAYBOOKS: list[dict[str, object]] = [
    {
        "code": "compromised-account",
        "title_es": "Cuenta comprometida",
        "title_en": "Compromised Account",
        "description_es": "Contención de identidad: revoca sesiones, bloquea cuenta y solicita cambio de contraseña/MFA.",
        "description_en": "Identity containment: revokes sessions, blocks account, and forces password/MFA reset.",
    },
    {
        "code": "compromised-endpoint",
        "title_es": "Endpoint comprometido o malware detectado",
        "title_en": "Compromised Endpoint or Malware Detected",
        "description_es": "Contención EDR/Host: recolecta evidencia, busca IoCs, aisla el host y pone archivos en cuarentena.",
        "description_en": "EDR/Host containment: collects evidence, searches IoCs, isolates host, and quarantines files.",
    },
    {
        "code": "phishing-malicious-email",
        "title_es": "Phishing y correo malicioso",
        "title_en": "Phishing and Malicious Email",
        "description_es": "Análisis de correo, eliminación masiva de mensajes similares en buzones y bloqueo de URL/Dominio.",
        "description_en": "Email analysis, mass removal of similar messages in mailboxes, and URL/Domain blocking.",
    },
    {
        "code": "ransomware-destructive",
        "title_es": "Ransomware o actividad destructiva",
        "title_en": "Ransomware or Destructive Activity",
        "description_es": "Procedimiento crítico de contención masiva, aislamiento de red, preservación de backups y gestión de crisis.",
        "description_en": "Critical mass containment procedure, network isolation, backup protection, and crisis management.",
    },
    {
        "code": "lateral-movement",
        "title_es": "Movimiento lateral",
        "title_en": "Lateral Movement",
        "description_es": "Correlación multi-fuente (identidad, host, red): rompe la cadena origen-destino y revoca sesiones.",
        "description_en": "Multi-source correlation (identity, host, network): breaks origin-destination chain and revokes sessions.",
    },
    {
        "code": "malicious-indicator",
        "title_es": "IP, dominio o indicador malicioso (IoC)",
        "title_en": "Malicious IP, Domain, or Indicator (IoC)",
        "description_es": "Enriquecimiento Threat Intel, búsqueda en todo el entorno y bloqueo temporal automático de IoCs.",
        "description_en": "Threat Intel enrichment, environment-wide search, and automatic temporary IoC blocking.",
    },
    {
        "code": "privilege-escalation",
        "title_es": "Escalamiento de privilegios o cuenta anómala",
        "title_en": "Privilege Escalation or Anomalous Privileged Account",
        "description_es": "Contraste con tickets de cambio autorizado, reversión de permisos y suspensión de cuenta privilegiada.",
        "description_en": "Contrast with authorized change tickets, privilege reversal, and privileged account suspension.",
    },
    {
        "code": "security-control-disabled",
        "title_es": "Desactivación de controles de seguridad",
        "title_en": "Security Controls Disabled",
        "description_es": "Detección de evasión: reactivación inmediata de EDR/Logs/Auditoría y elevación de riesgo.",
        "description_en": "Evasion detection: immediate reactivation of EDR/Logs/Audit and risk score elevation.",
    },
    {
        "code": "automated-enrichment",
        "title_es": "Enriquecimiento automático de incidentes",
        "title_en": "Automated Incident Enrichment",
        "description_es": "Playbook transversal: reúne activos, dueños, vulnerabilidades, reputación y mappings MITRE.",
        "description_en": "Transversal playbook: gathers assets, owners, vulnerabilities, reputation, and MITRE mappings.",
    },
    {
        "code": "escalation-notification",
        "title_es": "Escalamiento y notificación",
        "title_en": "Escalation and Notification",
        "description_es": "Playbook transversal: notifica por correo, Teams, Slack e ITSM según SLAs de severidad y tenant.",
        "description_en": "Transversal playbook: notifies via email, Teams, Slack, and ITSM based on severity and tenant SLAs.",
    },
    {
        "code": "evidence-preservation",
        "title_es": "Preservación de evidencia e inmutabilidad",
        "title_en": "Evidence Preservation and Immutability",
        "description_es": "Playbook transversal: sella alertas originales, hashes, snapshots y logs en almacén inmutable.",
        "description_en": "Transversal playbook: seals raw alerts, hashes, snapshots, and logs in an immutable store.",
    },
    {
        "code": "closure-controlled-learning",
        "title_es": "Cierre de incidente y aprendizaje controlado",
        "title_en": "Incident Closure and Controlled Learning",
        "description_es": "Playbook transversal: verifica contención, documenta causa raíz y propone mejoras con aprobación humana.",
        "description_en": "Transversal playbook: verifies containment, documents root cause, and proposes candidate memories with human approval.",
    },
]

ESSENTIAL_NATIVE_ACTIONS: dict[str, str] = {
    "compromised-account": "ticket.create",
    "compromised-endpoint": "endpoint.isolate_simulated",
    "phishing-malicious-email": "ticket.create",
    "ransomware-destructive": "notification.send",
    "lateral-movement": "incident.report.generate",
    "malicious-indicator": "ticket.create",
    "privilege-escalation": "notification.send",
    "security-control-disabled": "notification.send",
    "automated-enrichment": "incident.report.generate",
    "escalation-notification": "notification.send",
    "evidence-preservation": "incident.report.generate",
    "closure-controlled-learning": "incident.report.generate",
}

from cyrvanta.modules.playbooks.application.portable import (
    ActionStep,
    LocalizedDescription,
    LocalizedTitle,
    PortablePlaybookV1,
    portable_playbook_sha256,
)
from cyrvanta.modules.playbooks.infrastructure.action_registry import (
    ActionRegistry,
    ActionUnavailableError,
)
from cyrvanta.modules.playbooks.infrastructure.models import (
    AutomationEngineBindingModel,
    NativeActionBindingModel,
    PlaybookDefinitionModel,
    PlaybookExecutionModel,
    PlaybookVersionModel,
)
from cyrvanta.modules.playbooks.infrastructure.schema_registry import (
    SchemaReferenceUnknown,
    resolve_schema,
    validate_strict_object,
)
from cyrvanta.shared.config import Settings, get_settings
from cyrvanta.shared.database import SessionFactory, tenant_session
from cyrvanta.shared.domain.events import DomainEvent
from cyrvanta.shared.infrastructure.event_store import SqlEventStore

SENSITIVE_KEY = re.compile(
    r"(?:authorization|cookie|password|secret|token|api[_-]?key|private[_-]?key|credential)",
    re.IGNORECASE,
)


class PlaybookAdministrationNotFound(Exception):
    pass


class PlaybookAdministrationConflict(Exception):
    pass


PLAYBOOK_GOVERNANCE_TAXONOMY: dict[str, str] = {
    # 👥 FOUR_EYES: Acciones críticas de contención de identidad, aislamiento de hosts y respuesta a evasión/ransomware
    "simulate-user-block": "FOUR_EYES",
    "compromised-account": "FOUR_EYES",
    "simulate-host-isolation": "FOUR_EYES",
    "compromised-endpoint": "FOUR_EYES",
    "privilege-escalation": "FOUR_EYES",
    "ransomware-destructive": "FOUR_EYES",
    "lateral-movement": "FOUR_EYES",
    "security-control-disabled": "FOUR_EYES",
    # 👤 SINGLE: Notificaciones de incidentes críticos, tickets SecOps/ITSM y filtrado de IoCs
    "simulate-critical-incident-notification": "SINGLE",
    "escalation-notification": "SINGLE",
    "simulate-itsm-ticket-creation": "SINGLE",
    "phishing-malicious-email": "SINGLE",
    "malicious-indicator": "SINGLE",
    # ⚡ AUTOMATIC: Tareas transversales de análisis, preservación inmutable y aprendizaje
    "automated-enrichment": "AUTOMATIC",
    "evidence-preservation": "AUTOMATIC",
    "closure-controlled-learning": "AUTOMATIC",
}


class PlaybookAdministrationService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.registry = ActionRegistry()
        self.store = SqlEventStore(SessionFactory, self.settings.event_max_payload_bytes)

    async def list_definitions(self, tenant_id: UUID, *, limit: int, offset: int) -> DefinitionList:
        async with tenant_session(tenant_id) as session:
            await self._ensure_essential_definitions_seeded(session, tenant_id)
            items = list(
                (
                    await session.scalars(
                        select(PlaybookDefinitionModel)
                        .order_by(PlaybookDefinitionModel.created_at.desc())
                        .limit(limit)
                        .offset(offset)
                    )
                ).all()
            )
            total = int(await session.scalar(select(func.count(PlaybookDefinitionModel.id))) or 0)
            return DefinitionList(
                items=[await self._enriched_definition_response(session, item) for item in items],
                total=total,
            )

    async def _ensure_essential_definitions_seeded(
        self, session: AsyncSession, tenant_id: UUID
    ) -> None:
        for code, desired_approval_mode in PLAYBOOK_GOVERNANCE_TAXONOMY.items():
            existing_items = list(
                (
                    await session.scalars(
                        select(PlaybookDefinitionModel).where(PlaybookDefinitionModel.code == code)
                    )
                ).all()
            )
            for existing in existing_items:
                if existing.approval_mode != desired_approval_mode:
                    existing.approval_mode = desired_approval_mode

        for pb in ESSENTIAL_NATIVE_PLAYBOOKS:
            code = cast(str, pb["code"])
            existing = await session.scalar(
                select(PlaybookDefinitionModel).where(PlaybookDefinitionModel.code == code)
            )
            desired_approval_mode = PLAYBOOK_GOVERNANCE_TAXONOMY.get(code, "AUTOMATIC")

            if existing is None:
                def_model = PlaybookDefinitionModel(
                    tenant_id=tenant_id,
                    code=code,
                    name_es=cast(str, pb["title_es"]),
                    name_en=cast(str, pb["title_en"]),
                    description_es=cast(str, pb["description_es"]),
                    description_en=cast(str, pb["description_en"]),
                    action_type=code,
                    approval_mode=desired_approval_mode,
                )
                session.add(def_model)
                await session.flush()

                artifact_dict = {
                    "schema_version": "1.0",
                    "code": code,
                    "version": "1.0.0",
                    "title_i18n": {"es": pb["title_es"], "en": pb["title_en"]},
                    "description_i18n": {"es": pb["description_es"], "en": pb["description_en"]},
                    "execution_mode": "SIMULATED",
                    "impact_level": "MEDIUM",
                    "input_schema_ref": "security/incident-notification-input-v1",
                    "result_schema_ref": "security/incident-notification-result-v1",
                    "steps": [
                        {
                            "id": "step-1",
                            "type": "ACTION",
                            "action": ESSENTIAL_NATIVE_ACTIONS[code],
                            "action_version": "1.0.0",
                            "parameters": {},
                        }
                    ],
                    "edges": [],
                    "timeouts": {"overall_seconds": 60, "action_seconds": 30, "max_attempts": 1},
                }
                artifact = PortablePlaybookV1.model_validate(artifact_dict)
                digest = portable_playbook_sha256(artifact)
                version_model = PlaybookVersionModel(
                    tenant_id=tenant_id,
                    definition_id=def_model.id,
                    version="1.0.0",
                    impact="MODERATE",
                    classification="SYNTHETIC",
                    status="DRAFT",
                    approved_at=None,
                    workflow_code=code,
                    artifact_sha256=digest,
                    portable_artifact=artifact.model_dump(mode="json", exclude_none=True),
                    portable_schema_version="1.0",
                    input_schema=resolve_schema("security/incident-notification-input-v1"),
                    result_schema=resolve_schema("security/incident-notification-result-v1"),
                    timeout_seconds=60,
                )
                session.add(version_model)
                await session.flush()

        await session.flush()

    async def get_definition(self, tenant_id: UUID, definition_id: UUID) -> DefinitionResponse:
        async with tenant_session(tenant_id) as session:
            definition = await session.scalar(
                select(PlaybookDefinitionModel).where(PlaybookDefinitionModel.id == definition_id)
            )
            if definition is None:
                raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")
            return await self._enriched_definition_response(session, definition)

    async def create_definition(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        payload: DefinitionCreate,
        correlation_id: UUID,
    ) -> DefinitionResponse:
        async with tenant_session(tenant_id) as session:
            existing = await session.scalar(
                select(PlaybookDefinitionModel.id).where(
                    PlaybookDefinitionModel.code == payload.code
                )
            )
            if existing is not None:
                raise PlaybookAdministrationConflict("PLAYBOOK_STATE_CONFLICT")
            definition = PlaybookDefinitionModel(
                tenant_id=tenant_id,
                code=payload.code,
                name_es=payload.title_i18n.es,
                name_en=payload.title_i18n.en,
                description_es=payload.description_i18n.es,
                description_en=payload.description_i18n.en,
                action_type=payload.code,
            )
            session.add(definition)
            await session.flush()
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "playbook.definition.created",
                "playbook_definition",
                definition.id,
                {"code": payload.code},
            )
            return self._definition_response(definition)

    async def create_version(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        definition_id: UUID,
        payload: VersionCreate,
        correlation_id: UUID,
    ) -> VersionResponse:
        artifact = payload.artifact
        if artifact.execution_mode != "SIMULATED":
            raise PlaybookAdministrationConflict("PLAYBOOK_LIVE_DISABLED")
        input_schema = resolve_schema(artifact.input_schema_ref)
        result_schema = resolve_schema(artifact.result_schema_ref)
        self._validate_registered_actions(artifact)
        digest = portable_playbook_sha256(artifact)
        async with tenant_session(tenant_id) as session:
            definition = await session.scalar(
                select(PlaybookDefinitionModel).where(PlaybookDefinitionModel.id == definition_id)
            )
            if definition is None:
                raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")
            if definition.code != artifact.code:
                raise PlaybookAdministrationConflict("PLAYBOOK_INVALID")
            duplicate = await session.scalar(
                select(PlaybookVersionModel.id).where(
                    PlaybookVersionModel.definition_id == definition_id,
                    PlaybookVersionModel.version == artifact.version,
                )
            )
            if duplicate is not None:
                raise PlaybookAdministrationConflict("PLAYBOOK_IMMUTABLE")
            version = PlaybookVersionModel(
                tenant_id=tenant_id,
                definition_id=definition_id,
                version=artifact.version,
                impact="MODERATE" if artifact.impact_level == "MEDIUM" else artifact.impact_level,
                classification="SYNTHETIC",
                status="DRAFT",
                workflow_code=artifact.code,
                artifact_sha256=digest,
                portable_artifact=artifact.model_dump(mode="json", exclude_none=True),
                portable_schema_version="1.0",
                input_schema=input_schema,
                result_schema=result_schema,
                timeout_seconds=artifact.timeouts.overall_seconds,
                registered_by_user_id=actor_user_id,
            )
            session.add(version)
            await session.flush()
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "playbook.version.created",
                "playbook_version",
                version.id,
                {"definition_id": str(definition_id), "digest": digest},
            )
            return self._version_response(version)

    async def validate_version(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        version_id: UUID,
        correlation_id: UUID,
    ) -> tuple[VersionResponse, list[str]]:
        async with tenant_session(tenant_id) as session:
            version = await self._locked_version(session, version_id)
            errors = self._version_errors(version)
            if (
                version.impact in {"HIGH", "CRITICAL"}
                and version.registered_by_user_id == actor_user_id
            ):
                errors.append("PLAYBOOK_REVIEW_SEPARATION_REQUIRED")
            now = datetime.now(UTC)
            if not errors:
                version.validated_sha256 = version.artifact_sha256
                version.validated_at = now
                version.validated_by_user_id = actor_user_id
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "playbook.version.validated",
                "playbook_version",
                version.id,
                {"valid": not errors, "error_codes": errors},
                outcome="success" if not errors else "failure",
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                "security.playbook_version.validated",
                "playbook_version",
                version.id,
                "VALID" if not errors else "INVALID",
                {"digest": version.artifact_sha256},
            )
            return self._version_response(version), errors

    async def validate_connection_dependencies(
        self,
        *,
        tenant_id: UUID,
        version_id: UUID,
    ) -> list[dict[str, object]]:
        from cyrvanta.modules.integrations.application.resolver import ConnectionResolver

        resolver = ConnectionResolver()
        results: list[dict[str, object]] = []
        async with tenant_session(tenant_id) as session:
            version = await self._locked_version(session, version_id)
            try:
                artifact = self._artifact(version)
                for step in artifact.steps:
                    if isinstance(step, ActionStep):
                        capability = f"action.{step.action}"
                        res = await resolver.resolve(tenant_id, capability)
                        results.append(
                            {
                                "step_id": step.id,
                                "action": step.action,
                                "required_capability": capability,
                                "resolution_status": res.resolution_status,
                                "connection_id": res.connection_id,
                                "connector_type": res.connector_type,
                                "requires_approval": res.requires_approval,
                                "simulation_supported": res.simulation_supported,
                                "verification_supported": res.verification_supported,
                            }
                        )
            except Exception:
                pass
        return results

    async def publish_version(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        version_id: UUID,
        expected_digest: str,
        correlation_id: UUID,
    ) -> VersionResponse:
        async with tenant_session(tenant_id) as session:
            version = await self._locked_version(session, version_id)
            if version.status != "DRAFT":
                raise PlaybookAdministrationConflict("PLAYBOOK_IMMUTABLE")
            if expected_digest != version.artifact_sha256:
                raise PlaybookAdministrationConflict("PLAYBOOK_DIGEST_MISMATCH")
            if (
                version.validated_sha256 != version.artifact_sha256
                or version.validated_at is None
                or version.validated_by_user_id is None
            ):
                raise PlaybookAdministrationConflict("PLAYBOOK_INVALID")
            if version.impact in {"HIGH", "CRITICAL"} and actor_user_id in {
                version.registered_by_user_id,
                version.validated_by_user_id,
            }:
                raise PlaybookAdministrationConflict("PLAYBOOK_REVIEW_SEPARATION_REQUIRED")
            version.status = "APPROVED"
            version.approved_by_user_id = actor_user_id
            version.approved_at = datetime.now(UTC)
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "playbook.version.published",
                "playbook_version",
                version.id,
                {"digest": version.artifact_sha256},
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                "security.playbook_version.published",
                "playbook_version",
                version.id,
                "PUBLISHED",
                {"digest": version.artifact_sha256},
            )
            return self._version_response(version)

    async def dry_run(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        version_id: UUID,
        inputs: dict[str, object],
        correlation_id: UUID,
    ) -> DryRunResponse:
        async with tenant_session(tenant_id) as session:
            version = await session.scalar(
                select(PlaybookVersionModel).where(PlaybookVersionModel.id == version_id)
            )
            if version is None:
                raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")
            errors = self._version_errors(version)
            if not validate_strict_object(version.input_schema, inputs):
                errors.append("PLAYBOOK_INVALID")
            artifact = self._artifact(version)
            steps = [
                f"{step.type}:{step.id}"
                + (f":{step.action}@{step.action_version}" if isinstance(step, ActionStep) else "")
                for step in artifact.steps
            ]
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "playbook.version.dry_run",
                "playbook_version",
                version.id,
                {"valid": not errors, "step_count": len(steps)},
                outcome="success" if not errors else "failure",
            )
            return DryRunResponse(
                valid=not errors,
                engine_type="NATIVE",
                steps=steps,
                error_codes=sorted(set(errors)),
            )

    def list_actions(self) -> ActionList:
        items = [
            ActionResponse(
                code=item.code,
                version=item.version,
                modes=list(item.modes),
                impact=item.impact,
                timeout_seconds=item.timeout_seconds,
                retry_safe=item.retry_safe,
                cancellable=item.cancellable,
                egress=item.egress,
            )
            for item in self.registry.descriptors()
        ]
        return ActionList(items=items, total=len(items))

    async def list_bindings(self, tenant_id: UUID, *, limit: int, offset: int) -> BindingList:
        async with tenant_session(tenant_id) as session:
            items = list(
                (
                    await session.scalars(
                        select(AutomationEngineBindingModel)
                        .order_by(AutomationEngineBindingModel.created_at.desc())
                        .limit(limit)
                        .offset(offset)
                    )
                ).all()
            )
            total = int(
                await session.scalar(select(func.count(AutomationEngineBindingModel.id))) or 0
            )
            return BindingList(items=[self._binding_response(i) for i in items], total=total)

    async def create_binding(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        payload: BindingCreate,
        correlation_id: UUID,
    ) -> BindingResponse:
        async with tenant_session(tenant_id) as session:
            version = await session.scalar(
                select(PlaybookVersionModel).where(
                    PlaybookVersionModel.id == payload.playbook_version_id
                )
            )
            if version is None:
                raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")
            if version.status != "APPROVED":
                raise PlaybookAdministrationConflict("PLAYBOOK_INVALID")
            if payload.engine_type == "NATIVE":
                if self._version_errors(version):
                    raise PlaybookAdministrationConflict("PLAYBOOK_INVALID")
                adapter_workflow_id = webhook_path = key_id = None
                synchronized = await self._native_actions_ready(session, self._artifact(version))
            else:
                adapter_workflow_id = payload.adapter_workflow_id
                webhook_path = payload.webhook_path
                key_id = payload.key_id
                synchronized = False
            binding = AutomationEngineBindingModel(
                tenant_id=tenant_id,
                playbook_version_id=version.id,
                engine_type=payload.engine_type,
                instance_code=payload.instance_code,
                adapter_workflow_id=adapter_workflow_id,
                webhook_path=webhook_path,
                key_id=key_id,
                desired_digest=version.artifact_sha256,
                observed_digest=version.artifact_sha256 if synchronized else None,
                sync_status="SYNCHRONIZED" if synchronized else "PENDING",
                active=synchronized,
                last_verified_at=datetime.now(UTC) if synchronized else None,
            )
            session.add(binding)
            await session.flush()
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "playbook.binding.created",
                "automation_engine_binding",
                binding.id,
                {"engine_type": binding.engine_type, "active": binding.active},
            )
            return self._binding_response(binding)

    async def probe_binding(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        binding_id: UUID,
        correlation_id: UUID,
    ) -> BindingResponse:
        async with tenant_session(tenant_id) as session:
            binding = await session.scalar(
                select(AutomationEngineBindingModel)
                .where(AutomationEngineBindingModel.id == binding_id)
                .with_for_update()
            )
            if binding is None:
                raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")
            version = await session.scalar(
                select(PlaybookVersionModel).where(
                    PlaybookVersionModel.id == binding.playbook_version_id
                )
            )
            healthy = False
            if binding.engine_type == "NATIVE" and version is not None:
                healthy = not self._version_errors(version) and await self._native_actions_ready(
                    session, self._artifact(version)
                )
            binding.observed_digest = binding.desired_digest if healthy else None
            binding.sync_status = "SYNCHRONIZED" if healthy else "UNAVAILABLE"
            binding.active = healthy
            binding.last_verified_at = datetime.now(UTC)
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "playbook.binding.probed",
                "automation_engine_binding",
                binding.id,
                {"engine_type": binding.engine_type, "healthy": healthy},
                outcome="success" if healthy else "failure",
            )
            await self._event(
                session,
                tenant_id,
                correlation_id,
                "security.playbook_binding.probed",
                "automation_engine_binding",
                binding.id,
                "HEALTHY" if healthy else "UNAVAILABLE",
                {"engine_type": binding.engine_type},
            )
            return self._binding_response(binding)

    async def create_action_binding(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        payload: NativeActionBindingCreate,
        correlation_id: UUID,
    ) -> NativeActionBindingResponse:
        self._reject_sensitive_configuration(payload.configuration)
        if payload.connector_type != "SIMULATED" or payload.credential_key_id is not None:
            raise PlaybookAdministrationConflict("PLAYBOOK_EGRESS_DENIED")
        try:
            connector = self.registry.get(payload.action_code, payload.action_version)
        except ActionUnavailableError as exc:
            raise PlaybookAdministrationConflict("PLAYBOOK_ACTION_UNAVAILABLE") from exc
        validation = connector.validate_configuration(payload.configuration)
        if not validation.valid:
            raise PlaybookAdministrationConflict(validation.error_codes[0])
        digest = self._digest(payload.configuration)
        async with tenant_session(tenant_id) as session:
            existing = await session.scalar(
                select(NativeActionBindingModel.id).where(
                    NativeActionBindingModel.action_code == payload.action_code,
                    NativeActionBindingModel.action_version == payload.action_version,
                )
            )
            if existing is not None:
                raise PlaybookAdministrationConflict("PLAYBOOK_STATE_CONFLICT")
            binding = NativeActionBindingModel(
                tenant_id=tenant_id,
                action_code=payload.action_code,
                action_version=payload.action_version,
                connector_type="SIMULATED",
                credential_key_id=None,
                configuration=payload.configuration,
                configuration_sha256=digest,
                active=True,
                created_by_user_id=actor_user_id,
                last_verified_at=datetime.now(UTC),
            )
            session.add(binding)
            await session.flush()
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "playbook.native_action_binding.created",
                "native_action_binding",
                binding.id,
                {
                    "action_code": binding.action_code,
                    "action_version": binding.action_version,
                    "connector_type": "SIMULATED",
                },
            )
            return self._action_binding_response(binding)

    async def _native_actions_ready(
        self, session: AsyncSession, artifact: PortablePlaybookV1
    ) -> bool:
        for step in artifact.steps:
            if not isinstance(step, ActionStep):
                continue
            binding = await session.scalar(
                select(NativeActionBindingModel).where(
                    NativeActionBindingModel.action_code == step.action,
                    NativeActionBindingModel.action_version == step.action_version,
                    NativeActionBindingModel.connector_type == "SIMULATED",
                    NativeActionBindingModel.active.is_(True),
                    NativeActionBindingModel.last_verified_at.is_not(None),
                )
            )
            if binding is None or binding.configuration_sha256 != self._digest(
                binding.configuration
            ):
                return False
        return True

    def _version_errors(self, version: PlaybookVersionModel) -> list[str]:
        try:
            artifact = self._artifact(version)
            self._validate_registered_actions(artifact)
            resolve_schema(artifact.input_schema_ref)
            resolve_schema(artifact.result_schema_ref)
        except (
            ValueError,
            SchemaReferenceUnknown,
            ActionUnavailableError,
        ):
            return ["PLAYBOOK_INVALID"]
        if portable_playbook_sha256(artifact) != version.artifact_sha256:
            return ["PLAYBOOK_DIGEST_MISMATCH"]
        if artifact.execution_mode != "SIMULATED" or version.classification != "SYNTHETIC":
            return ["PLAYBOOK_LIVE_DISABLED"]
        return []

    def _validate_registered_actions(self, artifact: PortablePlaybookV1) -> None:
        for step in artifact.steps:
            if isinstance(step, ActionStep):
                descriptor = self.registry.get(step.action, step.action_version).describe()
                if "SIMULATED" not in descriptor.modes:
                    raise ActionUnavailableError("PLAYBOOK_ACTION_UNAVAILABLE")

    @staticmethod
    def _artifact(version: PlaybookVersionModel) -> PortablePlaybookV1:
        if version.portable_artifact is None or version.portable_schema_version != "1.0":
            raise ValueError("PLAYBOOK_INVALID")
        return PortablePlaybookV1.model_validate(version.portable_artifact)

    @staticmethod
    async def _locked_version(session: AsyncSession, version_id: UUID) -> PlaybookVersionModel:
        version = await session.scalar(
            select(PlaybookVersionModel)
            .where(PlaybookVersionModel.id == version_id)
            .with_for_update()
        )
        if version is None:
            raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")
        return version

    async def _enriched_definition_response(
        self, session: AsyncSession, item: PlaybookDefinitionModel
    ) -> DefinitionResponse:
        response = self._definition_response(item)
        version = await session.scalar(
            select(PlaybookVersionModel)
            .where(PlaybookVersionModel.definition_id == item.id)
            .order_by(PlaybookVersionModel.created_at.desc())
            .limit(1)
        )
        if version is None:
            return response
        binding = await session.scalar(
            select(AutomationEngineBindingModel)
            .where(AutomationEngineBindingModel.playbook_version_id == version.id)
            .order_by(
                AutomationEngineBindingModel.active.desc(),
                (AutomationEngineBindingModel.engine_type == "NATIVE").desc(),
                AutomationEngineBindingModel.created_at.desc(),
            )
            .limit(1)
        )
        execution = await session.scalar(
            select(PlaybookExecutionModel)
            .where(PlaybookExecutionModel.playbook_version_id == version.id)
            .order_by(PlaybookExecutionModel.created_at.desc())
            .limit(1)
        )
        artifact = self._artifact(version) if version.portable_artifact is not None else None
        required = version.input_schema.get("required", [])
        target_types = PLAYBOOK_INCIDENT_TYPES.get(item.code, ["all-incidents"])
        mitre = PLAYBOOK_MITRE_CODES.get(item.code, ["T1078"])
        rollback_info = PLAYBOOK_ROLLBACK_MAP.get(
            item.code,
            {
                "code": f"rollback-{item.code}",
                "es": f"Reversión segura del playbook {item.code}.",
                "en": f"Safe rollback for playbook {item.code}.",
            },
        )
        rollback_guidance = LocalizedDescription(es=rollback_info["es"], en=rollback_info["en"])
        policy_info = PLAYBOOK_AUTOMATION_POLICY_MAP.get(
            item.code,
            {
                "es": "Ejecución por defecto supervisada con aprobación humana según severidad.",
                "en": "Default supervised execution with human approval based on severity.",
            },
        )
        policy_guidance = LocalizedDescription(es=policy_info["es"], en=policy_info["en"])
        resolved_engine_type = (
            "N8N"
            if (binding is not None and binding.active and binding.engine_type == "N8N")
            else "NATIVE"
        )
        return response.model_copy(
            update={
                "latest_version": version.version,
                "publication_status": (
                    "PUBLISHED" if version.status == "APPROVED" else version.status
                ),
                "engine_type": resolved_engine_type,
                "binding_status": binding.sync_status if binding is not None else "SYNCHRONIZED",
                "binding_active": binding.active if binding is not None else True,
                "execution_mode": (
                    "SIMULATED" if version.classification == "SYNTHETIC" else "LIVE"
                ),
                "impact": "MEDIUM" if version.impact == "MODERATE" else version.impact,
                "required_parameters": (
                    [str(value) for value in required] if isinstance(required, list) else []
                ),
                "credential_aliases": (
                    list(artifact.credential_aliases) if artifact is not None else []
                ),
                "target_incident_types": target_types,
                "mitre_codes": mitre,
                "rollback_supported": True,
                "rollback_target_code": rollback_info["code"],
                "rollback_guidance_i18n": rollback_guidance,
                "automation_policy_i18n": policy_guidance,
                "approval_mode": getattr(item, "approval_mode", "AUTOMATIC") or "AUTOMATIC",
                "last_execution_status": (execution.status if execution is not None else None),
                "last_executed_at": (execution.created_at if execution is not None else None),
            }
        )

    async def update_approval_governance(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        definition_id: UUID,
        payload: UpdateApprovalGovernancePayload,
        correlation_id: UUID,
    ) -> DefinitionResponse:
        async with tenant_session(tenant_id) as session:
            definition = await session.scalar(
                select(PlaybookDefinitionModel).where(PlaybookDefinitionModel.id == definition_id)
            )
            if definition is None:
                raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")

            definition.approval_mode = payload.approval_mode
            await session.flush()
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "playbook.approval_governance.updated",
                "playbook_definition",
                definition.id,
                {
                    "approval_mode": payload.approval_mode,
                },
            )
            return await self._enriched_definition_response(session, definition)

    async def toggle_definition_binding(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        definition_id: UUID,
        payload: ToggleBindingPayload,
        correlation_id: UUID,
    ) -> DefinitionResponse:
        async with tenant_session(tenant_id) as session:
            definition = await session.scalar(
                select(PlaybookDefinitionModel).where(PlaybookDefinitionModel.id == definition_id)
            )
            if definition is None:
                raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")
            version = await session.scalar(
                select(PlaybookVersionModel)
                .where(
                    PlaybookVersionModel.definition_id == definition.id,
                    PlaybookVersionModel.status == "APPROVED",
                )
                .order_by(PlaybookVersionModel.created_at.desc())
                .limit(1)
            )
            if version is None:
                raise PlaybookAdministrationConflict("PLAYBOOK_INVALID")

            target_engine = payload.engine_type or "NATIVE"

            binding = await session.scalar(
                select(AutomationEngineBindingModel).where(
                    AutomationEngineBindingModel.playbook_version_id == version.id,
                    AutomationEngineBindingModel.engine_type == target_engine,
                )
            )

            desired_active = (
                payload.active
                if payload.active is not None
                else (not binding.active if binding else True)
            )

            if binding is None:
                if target_engine == "NATIVE":
                    synchronized = await self._native_actions_ready(
                        session, self._artifact(version)
                    )
                    binding = AutomationEngineBindingModel(
                        tenant_id=tenant_id,
                        playbook_version_id=version.id,
                        engine_type="NATIVE",
                        instance_code="cyrvanta-native",
                        desired_digest=version.artifact_sha256,
                        observed_digest=version.artifact_sha256 if synchronized else None,
                        sync_status="SYNCHRONIZED" if synchronized else "PENDING",
                        active=desired_active and synchronized,
                        last_verified_at=datetime.now(UTC) if synchronized else None,
                    )
                else:
                    raise PlaybookAdministrationConflict("PLAYBOOK_BINDING_UNAVAILABLE")
                session.add(binding)
            else:
                if desired_active:
                    self._assert_binding_activatable(binding)
                binding.active = desired_active

            if desired_active:
                other_bindings = list(
                    (
                        await session.scalars(
                            select(AutomationEngineBindingModel).where(
                                AutomationEngineBindingModel.playbook_version_id == version.id,
                                AutomationEngineBindingModel.id != binding.id,
                            )
                        )
                    ).all()
                )
                for ob in other_bindings:
                    ob.active = False

            await session.flush()
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "playbook.binding.toggled",
                "automation_engine_binding",
                binding.id,
                {
                    "definition_id": str(definition_id),
                    "engine_type": binding.engine_type,
                    "active": binding.active,
                },
            )
            return await self._enriched_definition_response(session, definition)

    @staticmethod
    def _definition_response(item: PlaybookDefinitionModel) -> DefinitionResponse:
        return DefinitionResponse(
            id=item.id,
            code=item.code,
            title_i18n=LocalizedTitle(es=item.name_es, en=item.name_en),
            description_i18n=LocalizedDescription(
                es=item.description_es or item.name_es,
                en=item.description_en or item.name_en,
            ),
            created_at=item.created_at,
            approval_mode=cast(
                Literal["AUTOMATIC", "SINGLE", "FOUR_EYES"],
                item.approval_mode or "AUTOMATIC",
            ),
        )

    @staticmethod
    def _version_response(item: PlaybookVersionModel) -> VersionResponse:
        return VersionResponse(
            id=item.id,
            definition_id=item.definition_id,
            version=item.version,
            status=cast(
                Literal["DRAFT", "PUBLISHED", "RETIRED"],
                "PUBLISHED" if item.status == "APPROVED" else item.status,
            ),
            engine_mode="SIMULATED" if item.classification == "SYNTHETIC" else "LIVE",
            impact="MEDIUM" if item.impact == "MODERATE" else item.impact,
            artifact_sha256=item.artifact_sha256,
            validated_sha256=item.validated_sha256,
            validated_at=item.validated_at,
            approved_at=item.approved_at,
            created_at=item.created_at,
        )

    @staticmethod
    def _binding_response(item: AutomationEngineBindingModel) -> BindingResponse:
        return BindingResponse(
            id=item.id,
            playbook_version_id=item.playbook_version_id,
            engine_type=cast(Literal["NATIVE", "N8N"], item.engine_type),
            instance_code=item.instance_code,
            sync_status=item.sync_status,
            active=item.active,
            desired_digest=item.desired_digest,
            observed_digest=item.observed_digest,
            last_verified_at=item.last_verified_at,
            created_at=item.created_at,
        )

    @staticmethod
    def _assert_binding_activatable(item: AutomationEngineBindingModel) -> None:
        if item.sync_status != "SYNCHRONIZED" or item.last_verified_at is None:
            raise PlaybookAdministrationConflict("PLAYBOOK_BINDING_UNAVAILABLE")
        if item.observed_digest is None or item.observed_digest != item.desired_digest:
            raise PlaybookAdministrationConflict("PLAYBOOK_BINDING_DRIFTED")

    @staticmethod
    def _action_binding_response(
        item: NativeActionBindingModel,
    ) -> NativeActionBindingResponse:
        return NativeActionBindingResponse(
            id=item.id,
            action_code=item.action_code,
            action_version=item.action_version,
            connector_type=item.connector_type,
            credential_configured=item.credential_key_id is not None,
            configuration_sha256=item.configuration_sha256,
            active=item.active,
            last_verified_at=item.last_verified_at,
            created_at=item.created_at,
        )

    @classmethod
    def _reject_sensitive_configuration(cls, value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if SENSITIVE_KEY.search(key):
                    raise PlaybookAdministrationConflict("PLAYBOOK_ACTION_CONFIG_INVALID")
                cls._reject_sensitive_configuration(nested)
        elif isinstance(value, list):
            for nested in value:
                cls._reject_sensitive_configuration(nested)

    @staticmethod
    def _digest(value: object) -> str:
        import hashlib
        import json

        return hashlib.sha256(
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()

    @staticmethod
    def _audit(
        session: AsyncSession,
        tenant_id: UUID,
        actor_user_id: UUID,
        correlation_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID,
        details: dict[str, object],
        *,
        outcome: str = "success",
    ) -> None:
        session.add(
            AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=outcome,
                correlation_id=correlation_id,
                details=details,
            )
        )

    async def _event(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        correlation_id: UUID,
        name: str,
        resource_type: str,
        resource_id: UUID,
        status: str,
        extra: dict[str, object],
    ) -> None:
        occurred_at = datetime.now(UTC)
        await self.store.recorder(session).add(
            DomainEvent.create(
                event_name=name,
                tenant_id=tenant_id,
                aggregate_type=resource_type,
                aggregate_id=resource_id,
                correlation_id=correlation_id,
                producer="playbooks",
                payload={
                    "tenant_id": str(tenant_id),
                    "resource_id": str(resource_id),
                    "occurred_at": occurred_at.isoformat(),
                    "status": status,
                    "correlation_id": str(correlation_id),
                    "causation_id": None,
                    **extra,
                },
                occurred_at=occurred_at,
            )
        )
