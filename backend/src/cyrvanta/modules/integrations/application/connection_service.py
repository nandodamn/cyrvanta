from __future__ import annotations

import asyncio
import json
import smtplib
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from cyrvanta.modules.directory.application.crypto import SecretCipher, SecretDecryptionError
from cyrvanta.modules.identity.infrastructure.models import AuditEventModel
from cyrvanta.modules.integrations.infrastructure.models import (
    IntegrationHealthHistoryModel,
    IntegrationModel,
)
from cyrvanta.shared.config import Settings, get_settings
from cyrvanta.shared.database import tenant_session

ConnectorType = Literal["SMTP", "HTTP_ALLOWLISTED", "N8N", "OPENSEARCH", "OLLAMA", "WAZUH"]

_REQUIRED: dict[str, frozenset[str]] = {
    "SMTP": frozenset({"host", "port", "from_address"}),
    "HTTP_ALLOWLISTED": frozenset({"base_url"}),
    "N8N": frozenset({"base_url", "api_key"}),
    "OPENSEARCH": frozenset({"base_url"}),
    "OLLAMA": frozenset({"base_url"}),
    "WAZUH": frozenset({"base_url", "username", "password"}),
}
_ALLOWED = frozenset({
    "host", "port", "username", "password", "from_address", "use_starttls",
    "base_url", "api_key", "bearer_token", "timeout_seconds",
})


class IntegrationConfigurationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connector_type: ConnectorType
    name: str = Field(min_length=1, max_length=200)
    configuration: dict[str, str | int | bool] = Field(default_factory=dict)
    enabled: bool = True


class IntegrationConnectionResponse(BaseModel):
    id: UUID
    connector_type: str
    name: str
    status: str
    configured: bool
    last_health_check_at: datetime | None
    last_error_code: str | None
    capabilities: list[str]


class IntegrationProbeResponse(BaseModel):
    id: UUID
    healthy: bool
    latency_ms: int
    error_code: str | None


class IntegrationConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StoredIntegrationCredential:
    reference: str
    values: dict[str, object]


class IntegrationConnectionService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.cipher = SecretCipher(self.settings.integration_encryption_key)

    async def list(self, tenant_id: UUID) -> list[IntegrationConnectionResponse]:
        async with tenant_session(tenant_id) as session:
            rows = list((await session.scalars(
                select(IntegrationModel)
                .where(IntegrationModel.tenant_id == tenant_id)
                .order_by(IntegrationModel.name)
            )).all())
            return [self._response(row) for row in rows]

    async def configure(
        self,
        *,
        tenant_id: UUID,
        actor_user_id: UUID,
        connection_id: str,
        payload: IntegrationConfigurationWrite,
        correlation_id: UUID,
    ) -> IntegrationConnectionResponse:
        values = dict(payload.configuration)
        self._validate(payload.connector_type, values)
        encrypted = self.cipher.encrypt(json.dumps(values, separators=(",", ":"), sort_keys=True))
        async with tenant_session(tenant_id) as session:
            row = None
            if connection_id != "new":
                try:
                    parsed_id = UUID(connection_id)
                except ValueError as exc:
                    raise IntegrationConfigurationError("INTEGRATION_ID_INVALID") from exc
                row = await session.scalar(select(IntegrationModel).where(
                    IntegrationModel.tenant_id == tenant_id,
                    IntegrationModel.id == parsed_id,
                ))
                if row is None:
                    raise IntegrationConfigurationError("INTEGRATION_NOT_FOUND")
            if row is None:
                row = IntegrationModel(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    connector_type=payload.connector_type,
                    name=payload.name,
                    status="pending_verification" if payload.enabled else "disabled",
                    configuration_schema_version="1.0",
                    configuration_encrypted=encrypted.encode(),
                    capabilities_snapshot={"capabilities": self._capabilities(payload.connector_type)},
                )
                session.add(row)
            else:
                row.connector_type = payload.connector_type
                row.name = payload.name
                row.status = "pending_verification" if payload.enabled else "disabled"
                row.configuration_schema_version = "1.0"
                row.configuration_encrypted = encrypted.encode()
                row.capabilities_snapshot = {
                    "capabilities": self._capabilities(payload.connector_type)
                }
                row.last_health_check_at = None
                row.last_error_code = None
                row.updated_at = datetime.now(UTC)
            await session.flush()
            session.add(AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action="integration.configuration.replaced",
                resource_type="integration",
                resource_id=row.id,
                outcome="success",
                correlation_id=correlation_id,
                details={"connector_type": row.connector_type, "secret_fields_redacted": True},
            ))
            return self._response(row)

    async def probe(
        self, *, tenant_id: UUID, actor_user_id: UUID, connection_id: UUID,
        correlation_id: UUID,
    ) -> IntegrationProbeResponse:
        async with tenant_session(tenant_id) as session:
            row = await session.scalar(select(IntegrationModel).where(
                IntegrationModel.tenant_id == tenant_id,
                IntegrationModel.id == connection_id,
            ))
            if row is None:
                raise IntegrationConfigurationError("INTEGRATION_NOT_FOUND")
            values = self._decrypt(row)
            started = perf_counter()
            healthy, error_code = await self._probe(row.connector_type, values)
            latency_ms = max(0, round((perf_counter() - started) * 1000))
            row.last_health_check_at = datetime.now(UTC)
            row.last_error_code = error_code
            row.status = "active" if healthy else "unhealthy"
            if healthy:
                row.last_successful_sync_at = row.last_health_check_at
            session.add(IntegrationHealthHistoryModel(
                tenant_id=tenant_id,
                integration_id=row.id,
                status="healthy" if healthy else "unhealthy",
                latency_ms=latency_ms,
                error_code=error_code,
                error_message_redacted=None,
            ))
            session.add(AuditEventModel(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action="integration.connection.probed",
                resource_type="integration",
                resource_id=row.id,
                outcome="success" if healthy else "failure",
                correlation_id=correlation_id,
                details={"connector_type": row.connector_type, "error_code": error_code},
            ))
            return IntegrationProbeResponse(
                id=row.id, healthy=healthy, latency_ms=latency_ms, error_code=error_code
            )

    async def resolve_credential(
        self, tenant_id: UUID, reference: str
    ) -> StoredIntegrationCredential:
        try:
            connection_id = UUID(reference)
        except ValueError as exc:
            raise IntegrationConfigurationError("PLAYBOOK_CREDENTIAL_UNAVAILABLE") from exc
        async with tenant_session(tenant_id) as session:
            row = await session.scalar(select(IntegrationModel).where(
                IntegrationModel.tenant_id == tenant_id,
                IntegrationModel.id == connection_id,
                IntegrationModel.status == "active",
                IntegrationModel.last_health_check_at.is_not(None),
                IntegrationModel.last_error_code.is_(None),
            ))
            if row is None:
                raise IntegrationConfigurationError("PLAYBOOK_CREDENTIAL_UNAVAILABLE")
            return StoredIntegrationCredential(str(row.id), self._decrypt(row))

    def _decrypt(self, row: IntegrationModel) -> dict[str, object]:
        try:
            value = json.loads(self.cipher.decrypt(row.configuration_encrypted.decode()))
        except (UnicodeDecodeError, json.JSONDecodeError, SecretDecryptionError) as exc:
            raise IntegrationConfigurationError("INTEGRATION_SECRET_UNAVAILABLE") from exc
        if not isinstance(value, dict):
            raise IntegrationConfigurationError("INTEGRATION_SECRET_UNAVAILABLE")
        return value

    def _validate(self, connector_type: str, values: dict[str, object]) -> None:
        unknown = set(values) - _ALLOWED
        missing = _REQUIRED[connector_type] - {
            key for key, value in values.items() if value not in ("", None)
        }
        if unknown or missing:
            raise IntegrationConfigurationError("INTEGRATION_CONFIGURATION_INVALID")
        if connector_type != "SMTP":
            url = str(values.get("base_url", ""))
            parsed = urlsplit(url)
            if parsed.scheme not in {"https", "http"} or not parsed.hostname:
                raise IntegrationConfigurationError("INTEGRATION_CONFIGURATION_INVALID")
            if self.settings.environment.casefold() == "production" and parsed.scheme != "https":
                raise IntegrationConfigurationError("INTEGRATION_TLS_REQUIRED")
        else:
            port = values.get("port")
            if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
                raise IntegrationConfigurationError("INTEGRATION_CONFIGURATION_INVALID")

    async def _probe(
        self, connector_type: str, values: dict[str, object]
    ) -> tuple[bool, str | None]:
        try:
            if connector_type == "SMTP":
                await asyncio.to_thread(self._probe_smtp, values)
                return True, None
            base_url = str(values["base_url"]).rstrip("/")
            path = {
                "OLLAMA": "/api/tags",
                "N8N": "/healthz",
                "OPENSEARCH": "/",
                "WAZUH": "/",
                "HTTP_ALLOWLISTED": "",
            }[connector_type]
            headers: dict[str, str] = {}
            token = values.get("api_key") or values.get("bearer_token")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            timeout = min(30, max(1, int(values.get("timeout_seconds", 10))))
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                response = await client.get(f"{base_url}{path}", headers=headers)
                response.raise_for_status()
            return True, None
        except (httpx.HTTPError, OSError, smtplib.SMTPException, ValueError, KeyError):
            return False, "INTEGRATION_PROBE_FAILED"

    @staticmethod
    def _probe_smtp(values: dict[str, object]) -> None:
        host, port = str(values["host"]), int(values["port"])
        timeout = min(30, max(1, int(values.get("timeout_seconds", 10))))
        with smtplib.SMTP(host, port, timeout=timeout) as client:
            client.ehlo()
            if bool(values.get("use_starttls", True)):
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            username = values.get("username")
            password = values.get("password")
            if username and password:
                client.login(str(username), str(password))

    @staticmethod
    def _capabilities(connector_type: str) -> list[str]:
        return {
            "SMTP": ["notification.send", "incident.report.deliver"],
            "HTTP_ALLOWLISTED": ["ticket.create", "webhook.invoke_allowlisted"],
            "N8N": ["playbook.dispatch"],
            "OPENSEARCH": ["telemetry.search"],
            "OLLAMA": ["analysis.ai"],
            "WAZUH": ["findings.ingest"],
        }[connector_type]

    @classmethod
    def _response(cls, row: IntegrationModel) -> IntegrationConnectionResponse:
        capabilities = row.capabilities_snapshot.get("capabilities", [])
        return IntegrationConnectionResponse(
            id=row.id,
            connector_type=row.connector_type,
            name=row.name,
            status=row.status,
            configured=bool(row.configuration_encrypted),
            last_health_check_at=row.last_health_check_at,
            last_error_code=row.last_error_code,
            capabilities=[str(item) for item in capabilities] if isinstance(capabilities, list) else [],
        )

