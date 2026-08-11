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
    simulation_supported: bool
    verification_supported: bool


# Core catalog of known capabilities and default risk policies
CAPABILITY_POLICIES: dict[str, CapabilityPolicy] = {
    "security.alert.read": {
        "connector_type": "wazuh",
        "requires_approval": False,
        "simulation_supported": True,
        "verification_supported": True,
    },
    "security.evidence.search": {
        "connector_type": "opensearch",
        "requires_approval": False,
        "simulation_supported": True,
        "verification_supported": True,
    },
    "ai.inference.execute": {
        "connector_type": "ollama",
        "requires_approval": False,
        "simulation_supported": True,
        "verification_supported": True,
    },
    "automation.workflow.execute": {
        "connector_type": "n8n",
        "requires_approval": False,
        "simulation_supported": True,
        "verification_supported": True,
    },
    "notification.email.send": {
        "connector_type": "smtp_lab",
        "requires_approval": False,
        "simulation_supported": True,
        "verification_supported": True,
    },
}


class ConnectionResolver:
    async def resolve(
        self,
        tenant_id: UUID,
        required_capability: str,
        environment: str = "laboratory",
        explicit_connection_id: UUID | None = None,
    ) -> ConnectionResolutionResult:
        del environment
        policy = CAPABILITY_POLICIES.get(required_capability)
        if policy is None:
            return ConnectionResolutionResult(
                resolution_status="not_resolved",
                connection_id=None,
                connector_type=None,
                capability=required_capability,
                selection_reason="capability_not_registered",
                requires_approval=False,
                simulation_supported=False,
                verification_supported=False,
                blocking=True,
            )

        async with tenant_session(tenant_id) as session:
            # Query configured active integrations for tenant
            stmt = select(IntegrationModel).where(
                IntegrationModel.tenant_id == tenant_id,
                IntegrationModel.status == "active",
            )
            if explicit_connection_id:
                stmt = stmt.where(IntegrationModel.id == explicit_connection_id)

            integrations = list((await session.scalars(stmt)).all())

            # Filter for matching capability or connector_type. Snapshot material is
            # untrusted JSON and must be narrowed before capability matching.
            matching: list[IntegrationModel] = []
            for integration in integrations:
                declared_capabilities: list[str] = []
                if isinstance(integration.capabilities_snapshot, dict):
                    declared = integration.capabilities_snapshot.get("declared")
                    if isinstance(declared, list):
                        declared_capabilities = [item for item in declared if isinstance(item, str)]
                if (
                    integration.connector_type == policy["connector_type"]
                    or required_capability in declared_capabilities
                ):
                    matching.append(integration)

            if matching:
                selected = matching[0]
                return ConnectionResolutionResult(
                    resolution_status="resolved",
                    connection_id=str(selected.id),
                    connector_type=selected.connector_type,
                    capability=required_capability,
                    selection_reason="tenant_healthy_authorized_connection",
                    requires_approval=policy["requires_approval"],
                    simulation_supported=policy["simulation_supported"],
                    verification_supported=policy["verification_supported"],
                    blocking=False,
                )

        return ConnectionResolutionResult(
            resolution_status="not_resolved",
            connection_id=None,
            connector_type=policy["connector_type"],
            capability=required_capability,
            selection_reason=(
                "explicit_connection_unavailable"
                if explicit_connection_id is not None
                else "tenant_connection_unavailable"
            ),
            requires_approval=policy["requires_approval"],
            simulation_supported=policy["simulation_supported"],
            verification_supported=policy["verification_supported"],
            blocking=True,
        )
