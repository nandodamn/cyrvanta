from dataclasses import dataclass
from typing import Literal
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


# Core catalog of known capabilities and default risk policies
CAPABILITY_POLICIES = {
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
    "identity.local_user.disable": {
        "connector_type": "windows_local",
        "requires_approval": True,
        "simulation_supported": True,
        "verification_supported": True,
    },
    "network.local_firewall.rule.create": {
        "connector_type": "windows_firewall",
        "requires_approval": True,
        "simulation_supported": True,
        "verification_supported": True,
    },
    "endpoint.isolate": {
        "connector_type": "defender",
        "requires_approval": True,
        "simulation_supported": True,
        "verification_supported": True,
    },
    "endpoint.release": {
        "connector_type": "defender",
        "requires_approval": True,
        "simulation_supported": True,
        "verification_supported": True,
    },
    "network.ip.block": {
        "connector_type": "palo_alto",
        "requires_approval": True,
        "simulation_supported": True,
        "verification_supported": True,
    },
    "network.ip.unblock": {
        "connector_type": "palo_alto",
        "requires_approval": True,
        "simulation_supported": True,
        "verification_supported": True,
    },
    "ticket.create": {
        "connector_type": "servicenow",
        "requires_approval": False,
        "simulation_supported": True,
        "verification_supported": True,
    },
    "threatintel.indicator.search": {
        "connector_type": "misp",
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
        policy = CAPABILITY_POLICIES.get(
            required_capability,
            {
                "connector_type": "generic",
                "requires_approval": False,
                "simulation_supported": True,
                "verification_supported": True,
            },
        )

        async with tenant_session(tenant_id) as session:
            # Query configured active integrations for tenant
            stmt = select(IntegrationModel).where(
                IntegrationModel.tenant_id == tenant_id,
                IntegrationModel.status != "disabled",
            )
            if explicit_connection_id:
                stmt = stmt.where(IntegrationModel.id == explicit_connection_id)

            integrations = list((await session.scalars(stmt)).all())

            # Filter for matching capability or connector_type
            matching = [
                integ
                for integ in integrations
                if integ.connector_type == policy["connector_type"]
                or required_capability in (integ.capabilities_snapshot.get("declared", []) if isinstance(integ.capabilities_snapshot, dict) else [])
            ]

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

        # Fallback resolution for system default laboratory connectors
        return ConnectionResolutionResult(
            resolution_status="resolved",
            connection_id=f"conn-lab-{policy['connector_type']}",
            connector_type=policy["connector_type"],
            capability=required_capability,
            selection_reason="laboratory_default_fallback",
            requires_approval=policy["requires_approval"],
            simulation_supported=policy["simulation_supported"],
            verification_supported=policy["verification_supported"],
            blocking=False,
        )
