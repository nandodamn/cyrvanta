from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
from cyrvanta.modules.integrations.application.connection_service import (
    CURRENT_CONFIGURATION_SCHEMA_VERSION,
)
from cyrvanta.modules.integrations.infrastructure.models import IntegrationModel
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
    is_strict_schema,
    resolve_schema,
    validate_strict_object,
)
from cyrvanta.shared.config import Settings, get_settings
from cyrvanta.shared.database import SessionFactory, tenant_session
from cyrvanta.shared.domain.events import DomainEvent
from cyrvanta.shared.infrastructure.event_store import SqlEventStore

ESSENTIAL_NATIVE_PLAYBOOKS: list[dict[str, object]] = [
    {
        "code": "compromised-account",
        "title_es": "Cuenta comprometida",
        "title_en": "Compromised Account",
        "description_es": (
            "Contención de identidad: revoca sesiones, bloquea cuenta y solicita "
            "cambio de contraseña/MFA."
        ),
        "description_en": (
            "Identity containment: revokes sessions, blocks account, and forces password/MFA reset."
        ),
    },
    {
        "code": "compromised-endpoint",
        "title_es": "Endpoint comprometido o malware detectado",
        "title_en": "Compromised Endpoint or Malware Detected",
        "description_es": (
            "Contención EDR/Host: recolecta evidencia, busca IoCs, aisla el host y "
            "pone archivos en cuarentena."
        ),
        "description_en": (
            "EDR/Host containment: collects evidence, searches IoCs, isolates host, "
            "and quarantines files."
        ),
    },
    {
        "code": "phishing-malicious-email",
        "title_es": "Phishing y correo malicioso",
        "title_en": "Phishing and Malicious Email",
        "description_es": (
            "Análisis de correo, eliminación masiva de mensajes similares en buzones "
            "y bloqueo de URL/Dominio."
        ),
        "description_en": (
            "Email analysis, mass removal of similar messages in mailboxes, and "
            "URL/Domain blocking."
        ),
    },
    {
        "code": "ransomware-destructive",
        "title_es": "Ransomware o actividad destructiva",
        "title_en": "Ransomware or Destructive Activity",
        "description_es": (
            "Procedimiento crítico de contención masiva, aislamiento de red, "
            "preservación de backups y gestión de crisis."
        ),
        "description_en": (
            "Critical mass containment procedure, network isolation, backup "
            "protection, and crisis management."
        ),
    },
    {
        "code": "lateral-movement",
        "title_es": "Movimiento lateral",
        "title_en": "Lateral Movement",
        "description_es": (
            "Correlación multi-fuente (identidad, host, red): rompe la cadena "
            "origen-destino y revoca sesiones."
        ),
        "description_en": (
            "Multi-source correlation (identity, host, network): breaks "
            "origin-destination chain and revokes sessions."
        ),
    },
    {
        "code": "malicious-indicator",
        "title_es": "IP, dominio o indicador malicioso (IoC)",
        "title_en": "Malicious IP, Domain, or Indicator (IoC)",
        "description_es": (
            "Enriquecimiento Threat Intel, búsqueda en todo el entorno y bloqueo "
            "temporal automático de IoCs."
        ),
        "description_en": (
            "Threat Intel enrichment, environment-wide search, and automatic "
            "temporary IoC blocking."
        ),
    },
    {
        "code": "privilege-escalation",
        "title_es": "Escalamiento de privilegios o cuenta anómala",
        "title_en": "Privilege Escalation or Anomalous Privileged Account",
        "description_es": (
            "Contraste con tickets de cambio autorizado, reversión de permisos y "
            "suspensión de cuenta privilegiada."
        ),
        "description_en": (
            "Contrast with authorized change tickets, privilege reversal, and "
            "privileged account suspension."
        ),
    },
    {
        "code": "security-control-disabled",
        "title_es": "Desactivación de controles de seguridad",
        "title_en": "Security Controls Disabled",
        "description_es": (
            "Detección de evasión: reactivación inmediata de EDR/Logs/Auditoría y "
            "elevación de riesgo."
        ),
        "description_en": (
            "Evasion detection: immediate reactivation of EDR/Logs/Audit and risk score elevation."
        ),
    },
    {
        "code": "automated-enrichment",
        "title_es": "Enriquecimiento automático de incidentes",
        "title_en": "Automated Incident Enrichment",
        "description_es": (
            "Playbook transversal: reúne activos, dueños, vulnerabilidades, "
            "reputación y mappings MITRE."
        ),
        "description_en": (
            "Transversal playbook: gathers assets, owners, vulnerabilities, "
            "reputation, and MITRE mappings."
        ),
    },
    {
        "code": "escalation-notification",
        "title_es": "Escalamiento y notificación",
        "title_en": "Escalation and Notification",
        "description_es": (
            "Playbook transversal: notifica por correo, Teams, Slack e ITSM según "
            "SLAs de severidad y tenant."
        ),
        "description_en": (
            "Transversal playbook: notifies via email, Teams, Slack, and ITSM based "
            "on severity and tenant SLAs."
        ),
    },
    {
        "code": "evidence-preservation",
        "title_es": "Preservación de evidencia e inmutabilidad",
        "title_en": "Evidence Preservation and Immutability",
        "description_es": (
            "Playbook transversal: sella alertas originales, hashes, snapshots y logs "
            "en almacén inmutable."
        ),
        "description_en": (
            "Transversal playbook: seals raw alerts, hashes, snapshots, and logs in "
            "an immutable store."
        ),
    },
    {
        "code": "closure-controlled-learning",
        "title_es": "Cierre de incidente y aprendizaje controlado",
        "title_en": "Incident Closure and Controlled Learning",
        "description_es": (
            "Playbook transversal: verifica contención, documenta causa raíz y "
            "propone mejoras con aprobación humana."
        ),
        "description_en": (
            "Transversal playbook: verifies containment, documents root cause, and "
            "proposes candidate memories with human approval."
        ),
    },
    {
        "code": "contain-and-document-incident",
        "title_es": "Contener y documentar incidente",
        "title_en": "Contain and Document Incident",
        "description_es": (
            "Transición interna real y auditada del incidente a estado contenido, "
            "con control de versión y aprobación."
        ),
        "description_en": (
            "Real audited internal transition of the incident to contained status, "
            "with optimistic locking and approval."
        ),
    },
    {
        "code": "notify-critical-incident",
        "title_es": "Notificar incidente crítico",
        "title_en": "Notify Critical Incident",
        "description_es": "Entrega SMTP real de una notificación tipada del incidente.",
        "description_en": "Real SMTP delivery of a typed incident notification.",
    },
    {
        "code": "create-security-ticket",
        "title_es": "Crear ticket de seguridad",
        "title_en": "Create Security Ticket",
        "description_es": "Creación real e idempotente de un ticket mediante HTTPS allowlisted.",
        "description_en": "Real idempotent ticket creation through allowlisted HTTPS.",
    },
    {
        "code": "incident-report-email",
        "title_es": "Enviar informe de incidente",
        "title_en": "Send Incident Report",
        "description_es": "Generación de un informe minimizado real y entrega por SMTP.",
        "description_en": "Generation of a real minimized incident report and SMTP delivery.",
    },
]

ESSENTIAL_NATIVE_ACTIONS: dict[str, str] = {
    "contain-and-document-incident": "incident.status.transition",
    "compromised-account": "ticket.create",
    "compromised-endpoint": "endpoint.isolate",
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
    "notify-critical-incident": "notification.send",
    "create-security-ticket": "ticket.create",
    "incident-report-email": "incident.report.generate",
}


IMPLEMENTED_REAL_PLAYBOOKS = {
    "contain-and-document-incident",
    "notify-critical-incident",
    "create-security-ticket",
    "incident-report-email",
}

SENSITIVE_KEY = re.compile(
    r"(?:authorization|cookie|password|secret|token|api[_-]?key|private[_-]?key|credential)",
    re.IGNORECASE,
)


class PlaybookAdministrationNotFound(Exception):
    pass


class PlaybookAdministrationConflict(Exception):
    pass


PLAYBOOK_GOVERNANCE_TAXONOMY: dict[str, str] = {
    "contain-and-document-incident": "SINGLE",
    # FOUR_EYES: critical identity containment and host-isolation actions,
    # including evasion and ransomware response.
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
    "notify-critical-incident": "SINGLE",
    "create-security-ticket": "SINGLE",
    "incident-report-email": "SINGLE",
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
                        .where(PlaybookDefinitionModel.tenant_id == tenant_id)
                        .order_by(PlaybookDefinitionModel.created_at.desc())
                        .limit(limit)
                        .offset(offset)
                    )
                ).all()
            )
            total = int(
                await session.scalar(
                    select(func.count(PlaybookDefinitionModel.id)).where(
                        PlaybookDefinitionModel.tenant_id == tenant_id
                    )
                )
                or 0
            )
            return DefinitionList(
                items=[await self._enriched_definition_response(session, item) for item in items],
                total=total,
            )

    async def _ensure_essential_definitions_seeded(
        self, session: AsyncSession, tenant_id: UUID
    ) -> None:
        for pb in ESSENTIAL_NATIVE_PLAYBOOKS:
            code = cast(str, pb["code"])
            desired_approval_mode = PLAYBOOK_GOVERNANCE_TAXONOMY.get(code, "AUTOMATIC")
            definition = await session.scalar(
                select(PlaybookDefinitionModel).where(
                    PlaybookDefinitionModel.tenant_id == tenant_id,
                    PlaybookDefinitionModel.code == code,
                )
            )
            if definition is None:
                definition = PlaybookDefinitionModel(
                    tenant_id=tenant_id,
                    code=code,
                    name_es=cast(str, pb["title_es"]),
                    name_en=cast(str, pb["title_en"]),
                    description_es=cast(str, pb["description_es"]),
                    description_en=cast(str, pb["description_en"]),
                    action_type=code,
                    approval_mode=desired_approval_mode,
                )
                session.add(definition)
                await session.flush()
            else:
                if not definition.description_es:
                    definition.description_es = cast(str, pb["description_es"])
                if not definition.description_en:
                    definition.description_en = cast(str, pb["description_en"])
                if not self._approval_satisfies_minimum(
                    definition.approval_mode or "AUTOMATIC", desired_approval_mode
                ):
                    definition.approval_mode = desired_approval_mode

            existing_versions = list(
                (
                    await session.scalars(
                        select(PlaybookVersionModel)
                        .where(
                            PlaybookVersionModel.tenant_id == tenant_id,
                            PlaybookVersionModel.definition_id == definition.id,
                        )
                        .order_by(PlaybookVersionModel.created_at.desc())
                    )
                ).all()
            )
            current_input_schema = resolve_schema("security/incident-notification-input-v1")
            current_result_schema = resolve_schema("security/incident-notification-result-v1")
            if any(
                version.classification == "LIVE"
                and version.status in {"DRAFT", "APPROVED"}
                and version.input_schema == current_input_schema
                and version.result_schema == current_result_schema
                for version in existing_versions
            ):
                continue
            version_number = self._next_patch_version(
                [version.version for version in existing_versions]
            )
            artifact = PortablePlaybookV1.model_validate(
                {
                    "schema_version": "1.0",
                    "code": code,
                    "version": version_number,
                    "title_i18n": {"es": pb["title_es"], "en": pb["title_en"]},
                    "description_i18n": {
                        "es": pb["description_es"],
                        "en": pb["description_en"],
                    },
                    "execution_mode": "LIVE",
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
                    "timeouts": {
                        "overall_seconds": 60,
                        "action_seconds": 30,
                        "max_attempts": 1,
                    },
                }
            )
            digest = portable_playbook_sha256(artifact)
            seeded_version = PlaybookVersionModel(
                tenant_id=tenant_id,
                definition_id=definition.id,
                version=version_number,
                impact="MODERATE",
                classification="LIVE",
                status="DRAFT",
                approved_at=None,
                workflow_code=code,
                artifact_sha256=digest,
                portable_artifact=artifact.model_dump(mode="json", exclude_none=True),
                portable_schema_version="1.0",
                input_schema=current_input_schema,
                result_schema=current_result_schema,
                timeout_seconds=60,
            )
            session.add(seeded_version)
            await session.flush()
            self._audit(
                session,
                tenant_id,
                None,
                uuid4(),
                "playbook.version.catalog_seeded",
                "playbook_version",
                seeded_version.id,
                {
                    "workflow_code": code,
                    "version": version_number,
                    "reason": "schema_upgrade" if existing_versions else "initial_seed",
                },
            )
        await session.flush()

    async def get_definition(self, tenant_id: UUID, definition_id: UUID) -> DefinitionResponse:
        async with tenant_session(tenant_id) as session:
            definition = await session.scalar(
                select(PlaybookDefinitionModel).where(
                    PlaybookDefinitionModel.tenant_id == tenant_id,
                    PlaybookDefinitionModel.id == definition_id,
                )
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
                    PlaybookDefinitionModel.tenant_id == tenant_id,
                    PlaybookDefinitionModel.code == payload.code,
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
        if artifact.execution_mode != "LIVE":
            raise PlaybookAdministrationConflict("PLAYBOOK_INVALID")
        input_schema = resolve_schema(artifact.input_schema_ref)
        result_schema = resolve_schema(artifact.result_schema_ref)
        self._validate_registered_actions(artifact)
        digest = portable_playbook_sha256(artifact)
        async with tenant_session(tenant_id) as session:
            definition = await session.scalar(
                select(PlaybookDefinitionModel).where(
                    PlaybookDefinitionModel.tenant_id == tenant_id,
                    PlaybookDefinitionModel.id == definition_id,
                )
            )
            if definition is None:
                raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")
            if definition.code != artifact.code:
                raise PlaybookAdministrationConflict("PLAYBOOK_INVALID")
            duplicate = await session.scalar(
                select(PlaybookVersionModel.id).where(
                    PlaybookVersionModel.tenant_id == tenant_id,
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
                classification="LIVE",
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
            version = await self._locked_version(session, tenant_id, version_id)
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
        results: list[dict[str, object]] = []
        async with tenant_session(tenant_id) as session:
            version = await self._locked_version(session, tenant_id, version_id)
            try:
                artifact = self._artifact(version)
                for step in artifact.steps:
                    if not isinstance(step, ActionStep):
                        continue
                    connector = self.registry.get(step.action, step.action_version)
                    descriptor = connector.describe()
                    binding = await session.scalar(
                        select(NativeActionBindingModel).where(
                            NativeActionBindingModel.tenant_id == tenant_id,
                            NativeActionBindingModel.action_code == step.action,
                            NativeActionBindingModel.action_version == step.action_version,
                            NativeActionBindingModel.active.is_(True),
                            NativeActionBindingModel.last_verified_at.is_not(None),
                        )
                    )
                    binding_ready = (
                        binding is not None
                        and binding.configuration_sha256 == self._digest(binding.configuration)
                    )
                    credential_id: UUID | None = None
                    credential_ready = descriptor.egress == "NONE"
                    if binding_ready and descriptor.egress != "NONE":
                        try:
                            credential_id = UUID(binding.credential_key_id or "")
                        except ValueError:
                            credential_ready = False
                        else:
                            credential_ready = (
                                await session.scalar(
                                    select(IntegrationModel.id).where(
                                        IntegrationModel.tenant_id == tenant_id,
                                        IntegrationModel.id == credential_id,
                                        IntegrationModel.status == "active",
                                        IntegrationModel.last_health_check_at.is_not(None),
                                        IntegrationModel.last_error_code.is_(None),
                                        IntegrationModel.configuration_schema_version
                                        == CURRENT_CONFIGURATION_SCHEMA_VERSION,
                                    )
                                )
                                is not None
                            )
                    ready = binding_ready and credential_ready
                    results.append(
                        {
                            "step_id": step.id,
                            "action": step.action,
                            "required_capability": step.action,
                            "resolution_status": "resolved" if ready else "not_resolved",
                            "connection_id": str(credential_id)
                            if credential_ready and credential_id
                            else None,
                            "connector_type": binding.connector_type
                            if binding is not None
                            else None,
                            "requires_approval": descriptor.impact in {"HIGH", "CRITICAL"},
                            "simulation_supported": False,
                            "verification_supported": True,
                            "blocking": not ready,
                        }
                    )
            except (ValueError, ActionUnavailableError) as exc:
                raise PlaybookAdministrationConflict("PLAYBOOK_INVALID") from exc
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
            version = await self._locked_version(session, tenant_id, version_id)
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
                select(PlaybookVersionModel).where(
                    PlaybookVersionModel.tenant_id == tenant_id,
                    PlaybookVersionModel.id == version_id,
                )
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
                        .where(AutomationEngineBindingModel.tenant_id == tenant_id)
                        .order_by(AutomationEngineBindingModel.created_at.desc())
                        .limit(limit)
                        .offset(offset)
                    )
                ).all()
            )
            total = int(
                await session.scalar(
                    select(func.count(AutomationEngineBindingModel.id)).where(
                        AutomationEngineBindingModel.tenant_id == tenant_id
                    )
                )
                or 0
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
                    PlaybookVersionModel.tenant_id == tenant_id,
                    PlaybookVersionModel.id == payload.playbook_version_id,
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
                synchronized = await self._native_actions_ready(
                    session, tenant_id, self._artifact(version)
                )
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
                .where(
                    AutomationEngineBindingModel.tenant_id == tenant_id,
                    AutomationEngineBindingModel.id == binding_id,
                )
                .with_for_update()
            )
            if binding is None:
                raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")
            version = await session.scalar(
                select(PlaybookVersionModel).where(
                    PlaybookVersionModel.tenant_id == tenant_id,
                    PlaybookVersionModel.id == binding.playbook_version_id,
                )
            )
            healthy = False
            if binding.engine_type == "NATIVE" and version is not None:
                healthy = not self._version_errors(version) and await self._native_actions_ready(
                    session, tenant_id, self._artifact(version)
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
        try:
            connector = self.registry.get(payload.action_code, payload.action_version)
        except ActionUnavailableError as exc:
            raise PlaybookAdministrationConflict("PLAYBOOK_ACTION_UNAVAILABLE") from exc
        descriptor = connector.describe()
        expected_connector = (
            "INTERNAL"
            if descriptor.egress == "NONE"
            else "HTTP_ALLOWLISTED"
            if descriptor.egress == "HTTPS"
            else "SMTP"
        )
        if payload.connector_type != expected_connector:
            raise PlaybookAdministrationConflict("PLAYBOOK_ACTION_CONFIG_INVALID")
        validation = connector.validate_configuration(payload.configuration)
        if not validation.valid:
            raise PlaybookAdministrationConflict(validation.error_codes[0])
        credential_id: UUID | None = None
        if expected_connector != "INTERNAL":
            try:
                credential_id = UUID(payload.credential_key_id or "")
            except ValueError as exc:
                raise PlaybookAdministrationConflict("PLAYBOOK_CREDENTIAL_UNAVAILABLE") from exc
        digest = self._digest(payload.configuration)
        async with tenant_session(tenant_id) as session:
            credential = None
            if credential_id is not None:
                credential = await session.scalar(
                    select(IntegrationModel).where(
                        IntegrationModel.tenant_id == tenant_id,
                        IntegrationModel.id == credential_id,
                        IntegrationModel.connector_type == payload.connector_type,
                        IntegrationModel.status == "active",
                        IntegrationModel.last_health_check_at.is_not(None),
                        IntegrationModel.last_error_code.is_(None),
                        IntegrationModel.configuration_schema_version
                        == CURRENT_CONFIGURATION_SCHEMA_VERSION,
                    )
                )
                if credential is None:
                    raise PlaybookAdministrationConflict("PLAYBOOK_CREDENTIAL_UNAVAILABLE")
            binding = await session.scalar(
                select(NativeActionBindingModel).where(
                    NativeActionBindingModel.tenant_id == tenant_id,
                    NativeActionBindingModel.action_code == payload.action_code,
                    NativeActionBindingModel.action_version == payload.action_version,
                )
            )
            if binding is None:
                binding = NativeActionBindingModel(
                    tenant_id=tenant_id,
                    action_code=payload.action_code,
                    action_version=payload.action_version,
                    connector_type=payload.connector_type,
                    credential_key_id=payload.credential_key_id,
                    configuration=payload.configuration,
                    configuration_sha256=digest,
                    active=False,
                    created_by_user_id=actor_user_id,
                    last_verified_at=None,
                )
                session.add(binding)
            else:
                binding.connector_type = payload.connector_type
                binding.credential_key_id = payload.credential_key_id
                binding.configuration = payload.configuration
                binding.configuration_sha256 = digest
                binding.active = False
                binding.last_verified_at = None
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
                    "connector_type": binding.connector_type,
                    "credential_reference": str(credential.id) if credential is not None else None,
                    "active": False,
                },
            )
            return self._action_binding_response(binding)

    async def verify_action_binding(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        binding_id: UUID,
        correlation_id: UUID,
    ) -> NativeActionBindingResponse:
        async with tenant_session(tenant_id) as session:
            binding = await session.scalar(
                select(NativeActionBindingModel).where(
                    NativeActionBindingModel.tenant_id == tenant_id,
                    NativeActionBindingModel.id == binding_id,
                )
            )
            if binding is None:
                raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")
            try:
                connector = self.registry.get(binding.action_code, binding.action_version)
                descriptor = connector.describe()
                credential_id = (
                    None if descriptor.egress == "NONE" else UUID(binding.credential_key_id or "")
                )
            except (ActionUnavailableError, ValueError) as exc:
                raise PlaybookAdministrationConflict("PLAYBOOK_CREDENTIAL_UNAVAILABLE") from exc
            validation = connector.validate_configuration(binding.configuration)
            if not validation.valid or binding.configuration_sha256 != self._digest(
                binding.configuration
            ):
                raise PlaybookAdministrationConflict("PLAYBOOK_ACTION_CONFIG_INVALID")
            credential = None
            if credential_id is not None:
                credential = await session.scalar(
                    select(IntegrationModel.id).where(
                        IntegrationModel.tenant_id == tenant_id,
                        IntegrationModel.id == credential_id,
                        IntegrationModel.connector_type == binding.connector_type,
                        IntegrationModel.status == "active",
                        IntegrationModel.last_health_check_at.is_not(None),
                        IntegrationModel.last_error_code.is_(None),
                        IntegrationModel.configuration_schema_version
                        == CURRENT_CONFIGURATION_SCHEMA_VERSION,
                    )
                )
                if credential is None:
                    raise PlaybookAdministrationConflict("PLAYBOOK_CREDENTIAL_UNAVAILABLE")
            binding.active = True
            binding.last_verified_at = datetime.now(UTC)
            await session.flush()
            self._audit(
                session,
                tenant_id,
                actor_user_id,
                correlation_id,
                "playbook.native_action_binding.verified",
                "native_action_binding",
                binding.id,
                {
                    "action_code": binding.action_code,
                    "connector_type": binding.connector_type,
                    "credential_reference": str(credential) if credential is not None else None,
                },
            )
            return self._action_binding_response(binding)

    async def _native_actions_ready(
        self, session: AsyncSession, tenant_id: UUID, artifact: PortablePlaybookV1
    ) -> bool:
        for step in artifact.steps:
            if not isinstance(step, ActionStep):
                continue
            binding = await session.scalar(
                select(NativeActionBindingModel).where(
                    NativeActionBindingModel.tenant_id == tenant_id,
                    NativeActionBindingModel.action_code == step.action,
                    NativeActionBindingModel.action_version == step.action_version,
                    NativeActionBindingModel.active.is_(True),
                    NativeActionBindingModel.last_verified_at.is_not(None),
                )
            )
            if binding is None or binding.configuration_sha256 != self._digest(
                binding.configuration
            ):
                return False
            try:
                connector = self.registry.get(step.action, step.action_version)
            except ActionUnavailableError:
                return False
            if connector.describe().egress != "NONE":
                try:
                    credential_id = UUID(binding.credential_key_id or "")
                except ValueError:
                    return False
                credential_ready = await session.scalar(
                    select(IntegrationModel.id).where(
                        IntegrationModel.tenant_id == tenant_id,
                        IntegrationModel.id == credential_id,
                        IntegrationModel.status == "active",
                        IntegrationModel.last_health_check_at.is_not(None),
                        IntegrationModel.last_error_code.is_(None),
                        IntegrationModel.configuration_schema_version
                        == CURRENT_CONFIGURATION_SCHEMA_VERSION,
                    )
                )
                if credential_ready is None:
                    return False
        return True

    def _version_errors(self, version: PlaybookVersionModel) -> list[str]:
        if version.workflow_code not in IMPLEMENTED_REAL_PLAYBOOKS:
            return ["PLAYBOOK_ACTION_UNAVAILABLE"]
        try:
            artifact = self._artifact(version)
            self._validate_registered_actions(artifact)
            resolve_schema(artifact.input_schema_ref)
            resolve_schema(artifact.result_schema_ref)
            if not is_strict_schema(version.input_schema) or not is_strict_schema(
                version.result_schema
            ):
                return ["PLAYBOOK_INVALID"]
        except (
            ValueError,
            SchemaReferenceUnknown,
            ActionUnavailableError,
        ):
            return ["PLAYBOOK_INVALID"]
        if portable_playbook_sha256(artifact) != version.artifact_sha256:
            return ["PLAYBOOK_DIGEST_MISMATCH"]
        if artifact.execution_mode != "LIVE" or version.classification != "LIVE":
            return ["PLAYBOOK_INVALID"]
        return []

    def _validate_registered_actions(self, artifact: PortablePlaybookV1) -> None:
        for step in artifact.steps:
            if isinstance(step, ActionStep):
                descriptor = self.registry.get(step.action, step.action_version).describe()
                if "LIVE" not in descriptor.modes:
                    raise ActionUnavailableError("PLAYBOOK_ACTION_UNAVAILABLE")

    @staticmethod
    def _artifact(version: PlaybookVersionModel) -> PortablePlaybookV1:
        if version.portable_artifact is None or version.portable_schema_version != "1.0":
            raise ValueError("PLAYBOOK_INVALID")
        return PortablePlaybookV1.model_validate(version.portable_artifact)

    @staticmethod
    async def _locked_version(
        session: AsyncSession, tenant_id: UUID, version_id: UUID
    ) -> PlaybookVersionModel:
        version = await session.scalar(
            select(PlaybookVersionModel)
            .where(
                PlaybookVersionModel.tenant_id == tenant_id,
                PlaybookVersionModel.id == version_id,
            )
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
            .where(
                PlaybookVersionModel.tenant_id == item.tenant_id,
                PlaybookVersionModel.definition_id == item.id,
            )
            .order_by(PlaybookVersionModel.created_at.desc())
            .limit(1)
        )
        if version is None:
            return response
        binding = await session.scalar(
            select(AutomationEngineBindingModel)
            .where(
                AutomationEngineBindingModel.tenant_id == item.tenant_id,
                AutomationEngineBindingModel.playbook_version_id == version.id,
            )
            .order_by(
                AutomationEngineBindingModel.active.desc(),
                (AutomationEngineBindingModel.engine_type == "NATIVE").desc(),
                AutomationEngineBindingModel.created_at.desc(),
            )
            .limit(1)
        )
        execution = await session.scalar(
            select(PlaybookExecutionModel)
            .where(
                PlaybookExecutionModel.tenant_id == item.tenant_id,
                PlaybookExecutionModel.playbook_version_id == version.id,
            )
            .order_by(PlaybookExecutionModel.created_at.desc())
            .limit(1)
        )
        artifact = self._artifact(version) if version.portable_artifact is not None else None
        required = version.input_schema.get("required", [])
        resolved_engine_type = (
            "N8N"
            if (binding is not None and binding.active and binding.engine_type == "N8N")
            else "NATIVE"
        )
        blocking_reasons: list[str] = []
        version_errors = self._version_errors(version)
        blocking_reasons.extend(version_errors)
        actions_ready = (
            artifact is not None
            and not version_errors
            and await self._native_actions_ready(session, item.tenant_id, artifact)
        )
        if version.status != "APPROVED":
            blocking_reasons.append("PLAYBOOK_NOT_PUBLISHED")
        if binding is None:
            blocking_reasons.append("PLAYBOOK_BINDING_UNAVAILABLE")
        elif (
            not binding.active
            or binding.sync_status != "SYNCHRONIZED"
            or binding.observed_digest != binding.desired_digest
        ):
            blocking_reasons.append("PLAYBOOK_BINDING_UNAVAILABLE")
        if not actions_ready:
            blocking_reasons.append("PLAYBOOK_CONFIGURATION_REQUIRED")
        if not self.settings.playbook_live_enabled or not self.settings.playbook_dispatch_enabled:
            blocking_reasons.append("PLAYBOOK_LIVE_DISABLED")
        blocking_reasons = list(dict.fromkeys(blocking_reasons))
        readiness_status = (
            "READY"
            if not blocking_reasons
            else "CONFIGURATION_REQUIRED"
            if "PLAYBOOK_CONFIGURATION_REQUIRED" in blocking_reasons
            else "DISABLED"
        )
        return response.model_copy(
            update={
                "latest_version": version.version,
                "latest_version_id": version.id,
                "latest_artifact_sha256": version.artifact_sha256,
                "publication_status": (
                    "PUBLISHED" if version.status == "APPROVED" else version.status
                ),
                "engine_type": resolved_engine_type,
                "binding_status": binding.sync_status if binding is not None else "PENDING",
                "binding_active": binding.active if binding is not None else False,
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
                "required_actions": (
                    [step.action for step in artifact.steps if isinstance(step, ActionStep)]
                    if artifact is not None
                    else []
                ),
                "target_incident_types": [],
                "mitre_codes": [],
                "rollback_supported": False,
                "rollback_target_code": None,
                "rollback_guidance_i18n": None,
                "automation_policy_i18n": None,
                "approval_mode": getattr(item, "approval_mode", "AUTOMATIC") or "AUTOMATIC",
                "last_execution_status": (execution.status if execution is not None else None),
                "last_executed_at": (execution.created_at if execution is not None else None),
                "readiness_status": readiness_status,
                "blocking_reasons": blocking_reasons,
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
                select(PlaybookDefinitionModel).where(
                    PlaybookDefinitionModel.tenant_id == tenant_id,
                    PlaybookDefinitionModel.id == definition_id,
                )
            )
            if definition is None:
                raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")

            minimum_mode = PLAYBOOK_GOVERNANCE_TAXONOMY.get(definition.code, "AUTOMATIC")
            if not self._approval_satisfies_minimum(payload.approval_mode, minimum_mode):
                raise PlaybookAdministrationConflict("PLAYBOOK_REVIEW_SEPARATION_REQUIRED")
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
                select(PlaybookDefinitionModel).where(
                    PlaybookDefinitionModel.tenant_id == tenant_id,
                    PlaybookDefinitionModel.id == definition_id,
                )
            )
            if definition is None:
                raise PlaybookAdministrationNotFound("PLAYBOOK_NOT_FOUND")
            version = await session.scalar(
                select(PlaybookVersionModel)
                .where(
                    PlaybookVersionModel.tenant_id == tenant_id,
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
                    AutomationEngineBindingModel.tenant_id == tenant_id,
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
                        session, tenant_id, self._artifact(version)
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
                if desired_active and target_engine == "NATIVE":
                    synchronized = await self._native_actions_ready(
                        session, tenant_id, self._artifact(version)
                    )
                    binding.observed_digest = version.artifact_sha256 if synchronized else None
                    binding.sync_status = "SYNCHRONIZED" if synchronized else "PENDING"
                    binding.last_verified_at = datetime.now(UTC) if synchronized else None
                if desired_active:
                    self._assert_binding_activatable(binding)
                binding.active = desired_active

            if desired_active:
                other_bindings = list(
                    (
                        await session.scalars(
                            select(AutomationEngineBindingModel).where(
                                AutomationEngineBindingModel.tenant_id == tenant_id,
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
    def _approval_satisfies_minimum(requested: str, minimum: str) -> bool:
        rank = {"AUTOMATIC": 0, "SINGLE": 1, "FOUR_EYES": 2}
        try:
            return rank[requested] >= rank[minimum]
        except KeyError:
            return False

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
    def _next_patch_version(existing: list[str]) -> str:
        parsed: list[tuple[int, int, int]] = []
        for value in existing:
            match = re.fullmatch(
                r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?",
                value,
            )
            if match is not None:
                parsed.append(tuple(int(part) for part in match.groups()))
        if not parsed:
            return "1.0.0"
        major, minor, patch = max(parsed)
        return f"{major}.{minor}.{patch + 1}"

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
        actor_user_id: UUID | None,
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
