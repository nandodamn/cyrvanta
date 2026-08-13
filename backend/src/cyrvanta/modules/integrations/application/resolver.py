from dataclasses import dataclass
from typing import Literal, TypedDict
from uuid import UUID

from sqlalchemy import select

from cyrvanta.modules.integrations.infrastructure.models import IntegrationModel
from cyrvanta.shared.database import tenant_session


@dataclass(frozen=True)
class ConnectionResolutionResult:
    resolution_status: Literal["resolved", "not_resolved"]
    connection_id: str | None
    connector_type: str | None
    capability: str
    selection_reason: str
    requires_approval: bool
    simulation_supported: bool
    verification_supported: bool
    blocking: bool = False


class CapabilityPolicy(TypedDict):
    connector_type: str
    requires_approval: bool
    verification_supported: bool


CAPABILITY_POLICIES: dict[str, CapabilityPolicy] = {
    "findings.ingest": {
        "connector_type": "WAZUH",
        "requires_approval": False,
        "verification_supported": True,
    },
    "telemetry.search": {
        "connector_type": "OPENSEARCH",
        "requires_approval": False,
        "verification_supported": True,
    },
    "analysis.ai": {
        "connector_type": "OLLAMA",
        "requires_approval": False,
        "verification_supported": True,
    },
    "playbook.dispatch": {
        "connector_type": "N8N",
        "requires_approval": False,
        "verification_supported": True,
    },
    "notification.send": {
        "connector_type": "SMTP",
        "requires_approval": True,
        "verification_supported": True,
    },
    "incident.report.deliver": {
        "connector_type": "SMTP",
        "requires_approval": True,
        "verification_supported": True,
    },
    "ticket.create": {
        "connector_type": "HTTP_ALLOWLISTED",
        "requires_approval": True,
        "verification_supported": True,
    },
    "webhook.invoke_allowlisted": {
        "connector_type": "HTTP_ALLOWLISTED",
        "requires_approval": True,
        "verification_supported": True,
    },
}


class ConnectionResolver:
    async def resolve(
        self,
        tenant_id: UUID,
        required_capability: str,
        environment: str = "live",
        explicit_connection_id: UUID | None = None,
    ) -> ConnectionResolutionResult:
        del environment
        policy = CAPABILITY_POLICIES.get(required_capability)
        if policy is None:
            return self._unavailable(required_capability, None, "capability_not_registered")

        async with tenant_session(tenant_id) as session:
            stmt = select(IntegrationModel).where(
                IntegrationModel.tenant_id == tenant_id,
                IntegrationModel.status == "active",
                IntegrationModel.last_health_check_at.is_not(None),
                IntegrationModel.last_error_code.is_(None),
            )
            if explicit_connection_id is not None:
                stmt = stmt.where(IntegrationModel.id == explicit_connection_id)

            integrations = list((await session.scalars(stmt)).all())
            matching: list[IntegrationModel] = []
            for integration in integrations:
                capabilities: list[str] = []
                if isinstance(integration.capabilities_snapshot, dict):
                    declared = integration.capabilities_snapshot.get("capabilities")
                    if isinstance(declared, list):
                        capabilities = [item for item in declared if isinstance(item, str)]
                if (
                    integration.connector_type == policy["connector_type"]
                    and required_capability in capabilities
                ):
                    matching.append(integration)

            if matching:
                selected = sorted(matching, key=lambda item: str(item.id))[0]
                return ConnectionResolutionResult(
                    resolution_status="resolved",
                    connection_id=str(selected.id),
                    connector_type=selected.connector_type,
                    capability=required_capability,
                    selection_reason="tenant_healthy_verified_connection",
                    requires_approval=policy["requires_approval"],
                    simulation_supported=False,
                    verification_supported=policy["verification_supported"],
                    blocking=False,
                )

        reason = (
            "explicit_connection_unavailable"
            if explicit_connection_id is not None
            else "tenant_connection_unavailable"
        )
        return self._unavailable(required_capability, policy, reason)

    @staticmethod
    def _unavailable(
        capability: str,
        policy: CapabilityPolicy | None,
        reason: str,
    ) -> ConnectionResolutionResult:
        return ConnectionResolutionResult(
            resolution_status="not_resolved",
            connection_id=None,
            connector_type=policy["connector_type"] if policy else None,
            capability=capability,
            selection_reason=reason,
            requires_approval=policy["requires_approval"] if policy else False,
            simulation_supported=False,
            verification_supported=policy["verification_supported"] if policy else False,
            blocking=True,
        )
