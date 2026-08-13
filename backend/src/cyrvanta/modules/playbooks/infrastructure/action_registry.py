from __future__ import annotations

import asyncio
import hashlib
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import unquote, urljoin, urlsplit
from uuid import UUID

import httpx
from sqlalchemy import select

from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
from cyrvanta.modules.incident.application.schemas import IncidentTransition
from cyrvanta.modules.incident.application.service import (
    IncidentConflict,
    IncidentNotFound,
    IncidentService,
    InvalidTransition,
)
from cyrvanta.modules.incident.infrastructure.models import IncidentModel
from cyrvanta.modules.integrations.application.connection_service import (
    StoredIntegrationCredential,
)
from cyrvanta.modules.operations.application.reporting import (
    IncidentReportService,
    IncidentReportStateConflict,
)
from cyrvanta.modules.playbooks.application.engine_ports import (
    ActionConnectorPort,
    ActionDescriptor,
    ActionResult,
    CredentialHandle,
    EngineContext,
    ProbeResult,
    ValidationResult,
)
from cyrvanta.shared.database import tenant_session
from cyrvanta.shared.target_validation import (
    contains_control_characters,
    is_safe_single_mailbox,
)

REAL_ACTIONS = (
    "incident.status.transition",
    "notification.send",
    "ticket.create",
    "incident.report.generate",
    "webhook.invoke_allowlisted",
)


class ActionUnavailableError(LookupError):
    pass


class RealActionConnector:
    def __init__(self, code: str) -> None:
        if code not in REAL_ACTIONS:
            raise ValueError("action is not registered")
        self._code = code

    def describe(self) -> ActionDescriptor:
        is_http = self._code in {"ticket.create", "webhook.invoke_allowlisted"}
        is_internal = self._code == "incident.status.transition"
        return ActionDescriptor(
            code=self._code,
            version="1.0.0",
            modes=("LIVE",),
            impact="MEDIUM",
            timeout_seconds=30,
            retry_safe=is_internal,
            cancellable=False,
            egress="NONE" if is_internal else "HTTPS" if is_http else "SMTP",
        )

    def validate_configuration(self, configuration: dict[str, object]) -> ValidationResult:
        invalid = ValidationResult(False, ("PLAYBOOK_ACTION_CONFIG_INVALID",))
        if self._code == "incident.status.transition":
            return (
                ValidationResult(True)
                if configuration == {"target_status": "contained"}
                else invalid
            )
        if self._code in {"notification.send", "incident.report.generate"}:
            required, allowed = {"to"}, {"to", "subject_prefix"}
        else:
            required, allowed = {"path"}, {"path", "method"}
        if set(configuration) - allowed or any(
            key not in configuration or configuration[key] in ("", None) for key in required
        ):
            return invalid
        if self._code in {"notification.send", "incident.report.generate"}:
            prefix = configuration.get("subject_prefix", "[Cyrvanta]")
            if (
                not is_safe_single_mailbox(configuration["to"])
                or not isinstance(prefix, str)
                or len(prefix) > 80
                or contains_control_characters(prefix)
            ):
                return invalid
            return ValidationResult(True)
        path = configuration["path"]
        method = configuration.get("method", "POST")
        if not isinstance(path, str) or not isinstance(method, str):
            return invalid
        try:
            parsed = urlsplit(path)
        except ValueError:
            return invalid
        decoded_path = parsed.path
        for _ in range(5):
            candidate = unquote(decoded_path)
            if candidate == decoded_path:
                break
            decoded_path = candidate
        else:
            return invalid
        if (
            path != path.strip()
            or not 1 <= len(path) <= 512
            or contains_control_characters(path)
            or not path.startswith("/")
            or parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or contains_control_characters(decoded_path)
            or "\\" in decoded_path
            or any(segment in {".", ".."} for segment in decoded_path.split("/"))
            or method.upper() != "POST"
        ):
            return invalid
        return ValidationResult(True)

    async def probe(self, context: EngineContext, configuration: dict[str, object]) -> ProbeResult:
        del context
        validation = self.validate_configuration(configuration)
        return ProbeResult(
            validation.valid, None if validation.valid else validation.error_codes[0]
        )

    async def execute(
        self,
        context: EngineContext,
        action_input: dict[str, object],
        configuration: dict[str, object],
        idempotency_key: str,
        credential_handle: CredentialHandle | None,
    ) -> ActionResult:
        validation = self.validate_configuration(configuration)
        if not validation.valid:
            return ActionResult(False, {}, validation.error_codes[0])
        if self._code == "incident.status.transition":
            inputs = action_input.get("inputs")
            if not isinstance(inputs, dict):
                return ActionResult(False, {}, "PLAYBOOK_ACTION_CONFIG_INVALID")
            try:
                incident_id = UUID(str(inputs["incident_id"]))
                actor_user_id = UUID(str(inputs["actor_user_id"]))
                expected_version = int(inputs["incident_version"])
                async with tenant_session(context.tenant_id) as session:
                    prior_effect = await session.scalar(
                        select(AuditEventModel.id).where(
                            AuditEventModel.tenant_id == context.tenant_id,
                            AuditEventModel.resource_type == "incident",
                            AuditEventModel.resource_id == incident_id,
                            AuditEventModel.action == "incident.status.changed",
                            AuditEventModel.correlation_id == context.correlation_id,
                        )
                    )
                    incident = await session.scalar(
                        select(IncidentModel).where(
                            IncidentModel.tenant_id == context.tenant_id,
                            IncidentModel.id == incident_id,
                        )
                    )
                if prior_effect is None:
                    incident = await IncidentService().transition(
                        context.tenant_id,
                        actor_user_id,
                        incident_id,
                        IncidentTransition(
                            expected_version=expected_version,
                            target_status="contained",
                            reason="Authorized Cyrvanta NATIVE playbook",
                        ),
                        context.correlation_id,
                    )
                elif (
                    incident is None
                    or incident.status != "contained"
                    or incident.version != expected_version + 1
                ):
                    return ActionResult(False, {}, "PLAYBOOK_STATE_CONFLICT")
            except (KeyError, ValueError, IncidentConflict, IncidentNotFound, InvalidTransition):
                return ActionResult(False, {}, "PLAYBOOK_ACTION_FAILED")
            receipt = hashlib.sha256(
                f"{idempotency_key}:{incident.id}:{incident.version}:contained".encode()
            ).hexdigest()[:24]
            return ActionResult(
                True,
                {
                    "effect": "applied",
                    "action_code": self._code,
                    "status": incident.status,
                    "incident_id": str(incident.id),
                    "incident_version": incident.version,
                    "receipt": receipt,
                },
                safe_detail="Incident transitioned to contained",
            )
        if not isinstance(credential_handle, StoredIntegrationCredential):
            return ActionResult(False, {}, "PLAYBOOK_CREDENTIAL_UNAVAILABLE")
        try:
            safe_payload = await self._safe_external_payload(context, action_input)
            if self._code in {"notification.send", "incident.report.generate"}:
                receipt = await self._send_email(
                    safe_payload,
                    configuration,
                    idempotency_key,
                    credential_handle.values,
                    attach_report=self._code == "incident.report.generate",
                )
                status = "DELIVERED"
            else:
                receipt = await self._post_http(
                    context,
                    safe_payload,
                    configuration,
                    idempotency_key,
                    credential_handle.values,
                )
                status = "CREATED" if self._code == "ticket.create" else "ACCEPTED"
        except (
            OSError,
            smtplib.SMTPException,
            httpx.HTTPError,
            ValueError,
            KeyError,
            IncidentReportStateConflict,
            IncidentNotFound,
        ):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_FAILED", "External action failed")
        return ActionResult(
            True,
            {"effect": "applied", "action_code": self._code, "status": status, "receipt": receipt},
            safe_detail="External action completed",
        )

    async def _safe_external_payload(
        self, context: EngineContext, action_input: dict[str, object]
    ) -> dict[str, object]:
        inputs = action_input.get("inputs")
        if not isinstance(inputs, dict):
            raise ValueError("missing execution inputs")
        incident_id = UUID(str(inputs["incident_id"]))
        expected_version = int(inputs["incident_version"])
        return await IncidentReportService().egress_snapshot(
            context.tenant_id,
            incident_id,
            expected_version=expected_version,
        )

    async def _send_email(
        self,
        action_input: dict[str, object],
        configuration: dict[str, object],
        idempotency_key: str,
        credential: dict[str, object],
        *,
        attach_report: bool,
    ) -> str:
        message = EmailMessage()
        prefix = str(configuration.get("subject_prefix", "[Cyrvanta]"))
        incident = action_input.get("incident")
        title = (
            str(incident.get("title"))
            if isinstance(incident, dict) and incident.get("title")
            else self._code
        )
        message["Subject"] = f"{prefix} {title}"[:240]
        message["From"] = str(credential["from_address"])
        message["To"] = str(configuration["to"])
        digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
        message["Message-ID"] = f"<{digest}@cyrvanta>"
        body = IncidentReportService.render_text(action_input)
        message.set_content(body[:100000])
        if attach_report:
            message.add_alternative(
                IncidentReportService.render_html(action_input)[:200000], subtype="html"
            )
        await asyncio.to_thread(self._smtp_send, credential, message)
        return hashlib.sha256(f"{idempotency_key}:{message['Message-ID']}".encode()).hexdigest()[
            :24
        ]

    @staticmethod
    def _smtp_send(credential: dict[str, object], message: EmailMessage) -> None:
        timeout = min(30, max(1, int(credential.get("timeout_seconds", 10))))
        with smtplib.SMTP(
            str(credential["host"]), int(credential["port"]), timeout=timeout
        ) as client:
            client.ehlo()
            if bool(credential.get("use_starttls", True)):
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            if credential.get("username") and credential.get("password"):
                client.login(str(credential["username"]), str(credential["password"]))
            client.send_message(message)

    async def _post_http(
        self,
        context: EngineContext,
        action_input: dict[str, object],
        configuration: dict[str, object],
        idempotency_key: str,
        credential: dict[str, object],
    ) -> str:
        base_url = str(credential["base_url"]).rstrip("/") + "/"
        target = urljoin(base_url, str(configuration["path"]).lstrip("/"))
        if urlsplit(target).netloc != urlsplit(base_url).netloc:
            raise ValueError("target escaped allowlisted origin")
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            "X-Cyrvanta-Tenant": str(context.tenant_id),
            "X-Cyrvanta-Correlation": str(context.correlation_id),
        }
        token = credential.get("api_key") or credential.get("bearer_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        timeout = min(30, max(1, int(credential.get("timeout_seconds", 10))))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.post(target, headers=headers, json=action_input)
            response.raise_for_status()
        remote_id = response.headers.get("Location") or response.headers.get("X-Request-Id")
        material = remote_id or f"{response.status_code}:{idempotency_key}"
        return hashlib.sha256(material.encode()).hexdigest()[:24]


class ActionRegistry:
    def __init__(self) -> None:
        self._connectors: dict[tuple[str, str], ActionConnectorPort] = {
            (code, "1.0.0"): RealActionConnector(code) for code in REAL_ACTIONS
        }

    def get(self, code: str, version: str) -> ActionConnectorPort:
        try:
            return self._connectors[(code, version)]
        except KeyError as exc:
            raise ActionUnavailableError("PLAYBOOK_ACTION_UNAVAILABLE") from exc

    def descriptors(self) -> tuple[ActionDescriptor, ...]:
        return tuple(
            connector.describe()
            for _, connector in sorted(self._connectors.items(), key=lambda item: item[0])
        )
