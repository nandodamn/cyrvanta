from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal


@dataclass(frozen=True)
class EnterpriseActionResult:
    status: Literal["succeeded", "simulated", "failed", "rolled_back"]
    capability: str
    target: str
    provider: str
    message: str
    verified: bool
    effective_at: datetime
    rollback_supported: bool


def _live_unavailable(
    capability: str,
    target: str,
    provider: str,
    *,
    rollback_supported: bool,
) -> EnterpriseActionResult:
    return EnterpriseActionResult(
        status="failed",
        capability=capability,
        target=target,
        provider=provider,
        message="LIVE_CONNECTOR_NOT_AVAILABLE",
        verified=False,
        effective_at=datetime.now(UTC),
        rollback_supported=rollback_supported,
    )


def _simulated(
    capability: str,
    target: str,
    provider: str,
    *,
    rollback: bool = False,
    rollback_supported: bool = True,
) -> EnterpriseActionResult:
    return EnterpriseActionResult(
        status="rolled_back" if rollback else "simulated",
        capability=capability,
        target=target,
        provider=provider,
        message="Simulated connector operation; no external system was changed.",
        verified=True,
        effective_at=datetime.now(UTC),
        rollback_supported=rollback_supported,
    )


class DefenderEndpointConnector:
    """Simulation-only placeholder for a future Defender adapter."""

    provider = "Microsoft Defender for Endpoint"

    async def isolate_host(
        self, device_id: str, is_simulation: bool = True
    ) -> EnterpriseActionResult:
        if not is_simulation:
            return _live_unavailable(
                "endpoint.isolate", device_id, self.provider, rollback_supported=True
            )
        return _simulated("endpoint.isolate", device_id, self.provider)

    async def release_host(
        self, device_id: str, is_simulation: bool = True
    ) -> EnterpriseActionResult:
        if not is_simulation:
            return _live_unavailable(
                "endpoint.release", device_id, self.provider, rollback_supported=True
            )
        return _simulated("endpoint.release", device_id, self.provider, rollback=True)


class CrowdStrikeFalconConnector:
    """Simulation-only placeholder for a future CrowdStrike adapter."""

    provider = "CrowdStrike Falcon"

    async def contain_host(
        self, aid: str, is_simulation: bool = True
    ) -> EnterpriseActionResult:
        if not is_simulation:
            return _live_unavailable(
                "endpoint.isolate", aid, self.provider, rollback_supported=True
            )
        return _simulated("endpoint.isolate", aid, self.provider)


class PaloAltoFirewallConnector:
    """Simulation-only placeholder for a future Palo Alto adapter."""

    provider = "Palo Alto PA-3200"

    async def block_ip(
        self, ip_address: str, is_simulation: bool = True
    ) -> EnterpriseActionResult:
        if not is_simulation:
            return _live_unavailable(
                "network.ip.block", ip_address, self.provider, rollback_supported=True
            )
        return _simulated("network.ip.block", ip_address, self.provider)

    async def unblock_ip(
        self, ip_address: str, is_simulation: bool = True
    ) -> EnterpriseActionResult:
        if not is_simulation:
            return _live_unavailable(
                "network.ip.unblock", ip_address, self.provider, rollback_supported=True
            )
        return _simulated("network.ip.unblock", ip_address, self.provider, rollback=True)


class FortinetFirewallConnector:
    """Simulation-only placeholder for a future Fortinet adapter."""

    provider = "Fortinet FortiGate"

    async def block_ip(
        self, ip_address: str, is_simulation: bool = True
    ) -> EnterpriseActionResult:
        if not is_simulation:
            return _live_unavailable(
                "network.ip.block", ip_address, self.provider, rollback_supported=True
            )
        return _simulated("network.ip.block", ip_address, self.provider)


class ServiceNowConnector:
    """Simulation-only placeholder for a future ServiceNow adapter."""

    async def create_incident_ticket(
        self, title: str, description: str, priority: str = "2"
    ) -> EnterpriseActionResult:
        del title, description, priority
        return _simulated(
            "ticket.create",
            "SIMULATED-SERVICENOW-TICKET",
            "ServiceNow ITSM",
            rollback_supported=False,
        )


class JiraServiceManagementConnector:
    """Simulation-only placeholder for a future Jira Service Management adapter."""

    async def create_ticket(
        self, summary: str, issue_type: str = "Incident"
    ) -> EnterpriseActionResult:
        del summary, issue_type
        return _simulated(
            "ticket.create",
            "SIMULATED-JSM-TICKET",
            "Jira Service Management",
            rollback_supported=False,
        )


class MispConnector:
    """Simulation-only placeholder for a future MISP adapter."""

    async def search_indicator(self, ioc_value: str) -> EnterpriseActionResult:
        return _simulated(
            "threatintel.indicator.search",
            ioc_value,
            "MISP Threat Intel",
            rollback_supported=False,
        )
