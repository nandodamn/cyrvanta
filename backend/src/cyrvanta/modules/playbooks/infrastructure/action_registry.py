from __future__ import annotations

import asyncio
import hashlib
import smtplib
import ssl
from datetime import UTC, datetime
from email.message import EmailMessage
from urllib.parse import unquote, urljoin, urlsplit
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select

from cyrvanta.modules.identity.infrastructure.models import AuditEventModel, UserModel
from cyrvanta.modules.incident.application.schemas import IncidentTransition
from cyrvanta.modules.incident.application.service import (
    IncidentConflict,
    IncidentNotFound,
    IncidentService,
    InvalidTransition,
)
from cyrvanta.modules.incident.infrastructure.models import IncidentModel
from cyrvanta.modules.integrations.application.connection_service import (
    IntegrationConfigurationError,
    IntegrationConnectionService,
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
    "account.disable",
    "account.enable",
    "endpoint.isolate",
    "host.isolate",
    "host.restore",
    "incident.report.generate",
    "incident.status.transition",
    "notification.send",
    "ticket.create",
    "webhook.invoke_allowlisted",
)

# Internal actions (no egress, retry-safe): no external credential required.
_INTERNAL_ACTIONS = frozenset({
    "incident.status.transition",
    "endpoint.isolate",
    "account.disable",
    "account.enable",
})

# Actions that call Wazuh Active Response (require WAZUH credential).
_WAZUH_ACTIONS = frozenset({"host.isolate", "host.restore"})

# SMTP actions.
_SMTP_ACTIONS = frozenset({"notification.send", "incident.report.generate"})

# HTTPS webhook/ticket actions.
_HTTP_ACTIONS = frozenset({"ticket.create", "webhook.invoke_allowlisted"})


class ActionUnavailableError(LookupError):
    pass


class RealActionConnector:
    def __init__(self, code: str) -> None:
        if code not in REAL_ACTIONS:
            raise ValueError("action is not registered")
        self._code = code

    def describe(self) -> ActionDescriptor:
        is_http = self._code in _HTTP_ACTIONS
        is_internal = self._code in _INTERNAL_ACTIONS
        is_wazuh = self._code in _WAZUH_ACTIONS
        is_high_impact = self._code in {
            "account.disable", "account.enable", "host.isolate", "host.restore"
        }
        retry_safe = self._code in {
            "incident.status.transition", "endpoint.isolate",
            "account.disable", "account.enable",
        }
        if is_internal:
            egress = "NONE"
        elif is_wazuh or is_http:
            egress = "HTTPS"
        else:
            egress = "SMTP"
        return ActionDescriptor(
            code=self._code,
            version="1.0.0",
            modes=("LIVE",),
            impact="HIGH" if is_high_impact else "MEDIUM",
            timeout_seconds=30,
            retry_safe=retry_safe,
            cancellable=False,
            egress=egress,
        )

    def validate_configuration(self, configuration: dict[str, object]) -> ValidationResult:
        invalid = ValidationResult(False, ("PLAYBOOK_ACTION_CONFIG_INVALID",))
        if self._code in {"incident.status.transition", "endpoint.isolate"}:
            return (
                ValidationResult(True)
                if configuration in ({"target_status": "contained"}, {"isolation_mode": "network"})
                or not configuration
                else invalid
            )
        # account.disable / account.enable / host.isolate / host.restore: no operator
        # configuration — all inputs come at runtime, isolation always runs the
        # reviewed cyrvanta-network-isolate AR script (see infrastructure/wazuh/agent/).
        if self._code in {"account.disable", "account.enable", "host.isolate", "host.restore"}:
            return ValidationResult(True) if not configuration else invalid
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
        if self._code in {"incident.status.transition", "endpoint.isolate"}:
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
        # ── Account containment: disable / enable user in Cyrvanta BD ─────────
        if self._code == "account.disable":
            return await self._execute_account_disable(context, action_input, idempotency_key)
        if self._code == "account.enable":
            return await self._execute_account_enable(context, action_input, idempotency_key)
        # ── Host isolation via Wazuh Active Response ───────────────────────────
        if self._code == "host.isolate":
            return await self._execute_host_isolate(
                context, action_input, configuration, idempotency_key, credential_handle
            )
        if self._code == "host.restore":
            return await self._execute_host_restore(
                context, action_input, configuration, idempotency_key, credential_handle
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
        except (OSError, smtplib.SMTPException, httpx.HTTPError):
            return ActionResult(
                False,
                {},
                "PLAYBOOK_ACTION_OUTCOME_UNKNOWN",
                "External action outcome is unknown",
            )
        except (ValueError, KeyError, IncidentReportStateConflict, IncidentNotFound):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_FAILED", "External action failed")
        return ActionResult(
            True,
            {"effect": "applied", "action_code": self._code, "status": status, "receipt": receipt},
            safe_detail="External action completed",
        )

    # ── Private helpers: account containment ───────────────────────────────────

    async def _execute_account_disable(
        self,
        context: EngineContext,
        action_input: dict[str, object],
        idempotency_key: str,
    ) -> ActionResult:
        """Disable a Cyrvanta user (is_active=False) and record an immutable audit snapshot."""
        inputs = action_input.get("inputs")
        if not isinstance(inputs, dict):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_CONFIG_INVALID")
        try:
            target_user_id = UUID(str(inputs["target_user_id"]))
            actor_user_id = UUID(str(inputs["actor_user_id"]))
        except (KeyError, ValueError):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_CONFIG_INVALID")
        async with tenant_session(context.tenant_id) as session:
            # Idempotency: check prior audit event for this correlation
            prior = await session.scalar(
                select(AuditEventModel.id).where(
                    AuditEventModel.tenant_id == context.tenant_id,
                    AuditEventModel.resource_id == target_user_id,
                    AuditEventModel.action == "user.account.disabled",
                    AuditEventModel.correlation_id == context.correlation_id,
                )
            )
            if prior is not None:
                # Already executed — return success (idempotent)
                receipt = hashlib.sha256(
                    f"{idempotency_key}:{target_user_id}:disabled".encode()
                ).hexdigest()[:24]
                return ActionResult(
                    True,
                    {"effect": "idempotent", "action_code": self._code,
                     "target_user_id": str(target_user_id), "receipt": receipt},
                    safe_detail="Account already disabled (idempotent)",
                )
            user = await session.scalar(
                select(UserModel).where(
                    UserModel.tenant_id == context.tenant_id,
                    UserModel.id == target_user_id,
                )
            )
            if user is None:
                return ActionResult(False, {}, "PLAYBOOK_ACTION_FAILED", "Target user not found")
            snapshot = {
                "was_active": user.is_active,
                "email": user.email,
                "display_name": user.display_name,
            }
            user.is_active = False
            user.updated_at = datetime.now(UTC)
            session.add(
                AuditEventModel(
                    id=uuid4(),
                    tenant_id=context.tenant_id,
                    actor_user_id=actor_user_id,
                    action="user.account.disabled",
                    resource_type="user",
                    resource_id=target_user_id,
                    outcome="SUCCESS",
                    correlation_id=context.correlation_id,
                    details={"playbook_action": self._code, "snapshot": snapshot},
                )
            )
            await session.flush()
        receipt = hashlib.sha256(
            f"{idempotency_key}:{target_user_id}:disabled".encode()
        ).hexdigest()[:24]
        return ActionResult(
            True,
            {
                "effect": "applied",
                "action_code": self._code,
                "target_user_id": str(target_user_id),
                "snapshot": snapshot,
                "receipt": receipt,
            },
            safe_detail="User account disabled",
        )

    async def _execute_account_enable(
        self,
        context: EngineContext,
        action_input: dict[str, object],
        idempotency_key: str,
    ) -> ActionResult:
        """Re-enable a Cyrvanta user (rollback of account.disable). Requires original_execution_id."""
        inputs = action_input.get("inputs")
        if not isinstance(inputs, dict):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_CONFIG_INVALID")
        try:
            target_user_id = UUID(str(inputs["target_user_id"]))
            actor_user_id = UUID(str(inputs["actor_user_id"]))
            original_execution_id = str(inputs["original_execution_id"])
        except (KeyError, ValueError):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_CONFIG_INVALID")
        async with tenant_session(context.tenant_id) as session:
            # Verify the original disable audit event exists (rollback traceability)
            original_event = await session.scalar(
                select(AuditEventModel).where(
                    AuditEventModel.tenant_id == context.tenant_id,
                    AuditEventModel.resource_id == target_user_id,
                    AuditEventModel.action == "user.account.disabled",
                )
            )
            if original_event is None:
                return ActionResult(
                    False, {}, "PLAYBOOK_STATE_CONFLICT",
                    "No prior account.disable audit event found for this user"
                )
            # Idempotency: check prior enable for this correlation
            prior = await session.scalar(
                select(AuditEventModel.id).where(
                    AuditEventModel.tenant_id == context.tenant_id,
                    AuditEventModel.resource_id == target_user_id,
                    AuditEventModel.action == "user.account.enabled",
                    AuditEventModel.correlation_id == context.correlation_id,
                )
            )
            if prior is not None:
                receipt = hashlib.sha256(
                    f"{idempotency_key}:{target_user_id}:enabled".encode()
                ).hexdigest()[:24]
                return ActionResult(
                    True,
                    {"effect": "idempotent", "action_code": self._code,
                     "target_user_id": str(target_user_id), "receipt": receipt},
                    safe_detail="Account already re-enabled (idempotent)",
                )
            user = await session.scalar(
                select(UserModel).where(
                    UserModel.tenant_id == context.tenant_id,
                    UserModel.id == target_user_id,
                )
            )
            if user is None:
                return ActionResult(False, {}, "PLAYBOOK_ACTION_FAILED", "Target user not found")
            user.is_active = True
            user.updated_at = datetime.now(UTC)
            session.add(
                AuditEventModel(
                    id=uuid4(),
                    tenant_id=context.tenant_id,
                    actor_user_id=actor_user_id,
                    action="user.account.enabled",
                    resource_type="user",
                    resource_id=target_user_id,
                    outcome="SUCCESS",
                    correlation_id=context.correlation_id,
                    details={
                        "playbook_action": self._code,
                        "original_execution_id": original_execution_id,
                        "rollback": True,
                    },
                )
            )
            await session.flush()
        receipt = hashlib.sha256(
            f"{idempotency_key}:{target_user_id}:enabled".encode()
        ).hexdigest()[:24]
        return ActionResult(
            True,
            {
                "effect": "applied",
                "action_code": self._code,
                "target_user_id": str(target_user_id),
                "original_execution_id": original_execution_id,
                "receipt": receipt,
            },
            safe_detail="User account re-enabled (rollback)",
        )

    # ── Private helpers: Wazuh Active Response ─────────────────────────────────

    async def _wazuh_authenticate(self, credential: dict[str, object]) -> str:
        """Obtain a short-lived Wazuh bearer token via basic authentication."""
        base_url = str(credential["base_url"]).rstrip("/")
        timeout = min(30, max(1, int(credential.get("timeout_seconds", 10))))
        auth = (str(credential["username"]), str(credential["password"]))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False,
                                     verify=True) as client:
            resp = await client.get(
                f"{base_url}/security/user/authenticate?raw=true",
                auth=auth,
            )
            resp.raise_for_status()
        token = resp.text.strip()
        if not token or len(token) > 4096 or contains_control_characters(token):
            raise ValueError("Invalid Wazuh authentication token")
        return token

    async def _execute_host_isolate(
        self,
        context: EngineContext,
        action_input: dict[str, object],
        configuration: dict[str, object],
        idempotency_key: str,
        credential_handle: CredentialHandle | None,
    ) -> ActionResult:
        """Send a Wazuh Active Response command to isolate a host from the network."""
        if not isinstance(credential_handle, StoredIntegrationCredential):
            return ActionResult(False, {}, "PLAYBOOK_CREDENTIAL_UNAVAILABLE")
        inputs = action_input.get("inputs")
        if not isinstance(inputs, dict):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_CONFIG_INVALID")
        try:
            target_agent_id = str(inputs["target_agent_id"])
            actor_user_id = UUID(str(inputs["actor_user_id"]))
        except (KeyError, ValueError):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_CONFIG_INVALID")
        # Validate agent_id format: 3-digit Wazuh ID or full UUID
        if not target_agent_id or len(target_agent_id) > 64 or contains_control_characters(target_agent_id):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_CONFIG_INVALID")
        credential = credential_handle.values
        base_url = str(credential["base_url"]).rstrip("/")
        timeout = min(30, max(1, int(credential.get("timeout_seconds", 10))))
        async with tenant_session(context.tenant_id) as session:
            # Idempotency: check prior audit event
            prior = await session.scalar(
                select(AuditEventModel.id).where(
                    AuditEventModel.tenant_id == context.tenant_id,
                    AuditEventModel.action == "host.network.isolated",
                    AuditEventModel.correlation_id == context.correlation_id,
                )
            )
            if prior is not None:
                receipt = hashlib.sha256(
                    f"{idempotency_key}:{target_agent_id}:isolated".encode()
                ).hexdigest()[:24]
                return ActionResult(
                    True,
                    {"effect": "idempotent", "action_code": self._code,
                     "target_agent_id": target_agent_id, "receipt": receipt},
                    safe_detail="Host already isolated (idempotent)",
                )
        try:
            token = await self._wazuh_authenticate(credential)
            ar_payload = {
                "command": "!cyrvanta-network-isolate",
                "arguments": ["add", str(context.correlation_id)],
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Cyrvanta-Correlation": str(context.correlation_id),
            }
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False,
                                         verify=True) as client:
                resp = await client.put(
                    f"{base_url}/active-response",
                    params={"agents_list": target_agent_id},
                    headers=headers,
                    json=ar_payload,
                )
                resp.raise_for_status()
                body = resp.json()
            if body.get("error") or body["data"]["total_failed_items"] > 0:
                return ActionResult(False, {}, "PLAYBOOK_ACTION_FAILED",
                                    "Wazuh rejected the active-response command")
            wazuh_task_id = resp.headers.get("X-Request-Id", "")
        except httpx.HTTPError:
            return ActionResult(False, {}, "PLAYBOOK_ACTION_OUTCOME_UNKNOWN",
                                "Wazuh AR isolation command outcome unknown")
        except (ValueError, KeyError):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_FAILED")
        # Write audit event
        async with tenant_session(context.tenant_id) as session:
            session.add(
                AuditEventModel(
                    id=uuid4(),
                    tenant_id=context.tenant_id,
                    actor_user_id=actor_user_id,
                    action="host.network.isolated",
                    resource_type="wazuh_agent",
                    resource_id=None,
                    outcome="SUCCESS",
                    correlation_id=context.correlation_id,
                    details={
                        "playbook_action": self._code,
                        "target_agent_id": target_agent_id,
                        "wazuh_task_id": wazuh_task_id,
                    },
                )
            )
            await session.flush()
        receipt = hashlib.sha256(
            f"{idempotency_key}:{target_agent_id}:isolated".encode()
        ).hexdigest()[:24]
        return ActionResult(
            True,
            {
                "effect": "applied",
                "action_code": self._code,
                "target_agent_id": target_agent_id,
                "wazuh_task_id": wazuh_task_id,
                "receipt": receipt,
            },
            safe_detail="Host network isolated via Wazuh AR",
        )

    async def _execute_host_restore(
        self,
        context: EngineContext,
        action_input: dict[str, object],
        configuration: dict[str, object],
        idempotency_key: str,
        credential_handle: CredentialHandle | None,
    ) -> ActionResult:
        """Send a Wazuh Active Response command to restore host network (rollback of host.isolate)."""
        if not isinstance(credential_handle, StoredIntegrationCredential):
            return ActionResult(False, {}, "PLAYBOOK_CREDENTIAL_UNAVAILABLE")
        inputs = action_input.get("inputs")
        if not isinstance(inputs, dict):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_CONFIG_INVALID")
        try:
            target_agent_id = str(inputs["target_agent_id"])
            actor_user_id = UUID(str(inputs["actor_user_id"]))
            original_execution_id = str(inputs["original_execution_id"])
        except (KeyError, ValueError):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_CONFIG_INVALID")
        if not target_agent_id or len(target_agent_id) > 64 or contains_control_characters(target_agent_id):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_CONFIG_INVALID")
        async with tenant_session(context.tenant_id) as session:
            # Verify prior isolation event exists (rollback traceability)
            original_event = await session.scalar(
                select(AuditEventModel).where(
                    AuditEventModel.tenant_id == context.tenant_id,
                    AuditEventModel.action == "host.network.isolated",
                    AuditEventModel.details["target_agent_id"].astext == target_agent_id,
                )
            )
            if original_event is None:
                return ActionResult(
                    False, {}, "PLAYBOOK_STATE_CONFLICT",
                    "No prior host.isolate audit event found for this agent"
                )
            # Idempotency
            prior = await session.scalar(
                select(AuditEventModel.id).where(
                    AuditEventModel.tenant_id == context.tenant_id,
                    AuditEventModel.action == "host.network.restored",
                    AuditEventModel.correlation_id == context.correlation_id,
                )
            )
            if prior is not None:
                receipt = hashlib.sha256(
                    f"{idempotency_key}:{target_agent_id}:restored".encode()
                ).hexdigest()[:24]
                return ActionResult(
                    True,
                    {"effect": "idempotent", "action_code": self._code,
                     "target_agent_id": target_agent_id, "receipt": receipt},
                    safe_detail="Host already restored (idempotent)",
                )
        credential = credential_handle.values
        base_url = str(credential["base_url"]).rstrip("/")
        timeout = min(30, max(1, int(credential.get("timeout_seconds", 10))))
        try:
            token = await self._wazuh_authenticate(credential)
            ar_payload = {
                "command": "!cyrvanta-network-isolate",
                "arguments": ["delete", str(context.correlation_id)],
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Cyrvanta-Correlation": str(context.correlation_id),
            }
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False,
                                         verify=True) as client:
                resp = await client.put(
                    f"{base_url}/active-response",
                    params={"agents_list": target_agent_id},
                    headers=headers,
                    json=ar_payload,
                )
                resp.raise_for_status()
                body = resp.json()
            if body.get("error") or body["data"]["total_failed_items"] > 0:
                return ActionResult(False, {}, "PLAYBOOK_ACTION_FAILED",
                                    "Wazuh rejected the active-response command")
            wazuh_task_id = resp.headers.get("X-Request-Id", "")
        except httpx.HTTPError:
            return ActionResult(False, {}, "PLAYBOOK_ACTION_OUTCOME_UNKNOWN",
                                "Wazuh AR restore command outcome unknown")
        except (ValueError, KeyError):
            return ActionResult(False, {}, "PLAYBOOK_ACTION_FAILED")
        # Write audit event
        async with tenant_session(context.tenant_id) as session:
            session.add(
                AuditEventModel(
                    id=uuid4(),
                    tenant_id=context.tenant_id,
                    actor_user_id=actor_user_id,
                    action="host.network.restored",
                    resource_type="wazuh_agent",
                    resource_id=None,
                    outcome="SUCCESS",
                    correlation_id=context.correlation_id,
                    details={
                        "playbook_action": self._code,
                        "target_agent_id": target_agent_id,
                        "wazuh_task_id": wazuh_task_id,
                        "original_execution_id": original_execution_id,
                        "rollback": True,
                    },
                )
            )
            await session.flush()
        receipt = hashlib.sha256(
            f"{idempotency_key}:{target_agent_id}:restored".encode()
        ).hexdigest()[:24]
        return ActionResult(
            True,
            {
                "effect": "applied",
                "action_code": self._code,
                "target_agent_id": target_agent_id,
                "original_execution_id": original_execution_id,
                "wazuh_task_id": wazuh_task_id,
                "receipt": receipt,
            },
            safe_detail="Host network restored via Wazuh AR (rollback)",
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
