import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConnectorActionResult:
    status: Literal["succeeded", "simulated", "failed", "rolled_back"]
    capability: str
    target: str
    message: str
    verified: bool
    effective_at: datetime
    rollback_supported: bool


def _live_unavailable(
    capability: str, target: str, *, rollback_supported: bool
) -> ConnectorActionResult:
    return ConnectorActionResult(
        status="failed",
        capability=capability,
        target=target,
        message="LIVE_CONNECTOR_NOT_AVAILABLE",
        verified=False,
        effective_at=datetime.now(UTC),
        rollback_supported=rollback_supported,
    )


class SmtpLabConnector:
    """Simulation-only SMTP sink that never transmits a message."""

    def __init__(self, host: str = "127.0.0.1", port: int = 1025) -> None:
        self.host = host
        self.port = port

    async def send_email(
        self, recipient: str, subject: str, body: str
    ) -> ConnectorActionResult:
        del subject, body
        logger.info("[SMTP-LAB] Captured a simulated email")
        return ConnectorActionResult(
            status="simulated",
            capability="notification.email.send",
            target=recipient,
            message="Simulated email captured by the laboratory sink.",
            verified=True,
            effective_at=datetime.now(UTC),
            rollback_supported=False,
        )


class WindowsLocalUserConnector:
    """Simulation-only placeholder; local account mutation is not authorized."""

    async def disable_user(
        self, username: str, is_simulation: bool = True
    ) -> ConnectorActionResult:
        if not is_simulation:
            return _live_unavailable(
                "identity.local_user.disable", username, rollback_supported=True
            )
        return ConnectorActionResult(
            status="simulated",
            capability="identity.local_user.disable",
            target=username,
            message="Simulated local-user disable; no account was changed.",
            verified=True,
            effective_at=datetime.now(UTC),
            rollback_supported=True,
        )

    async def enable_user(
        self, username: str, is_simulation: bool = True
    ) -> ConnectorActionResult:
        if not is_simulation:
            return _live_unavailable(
                "identity.local_user.enable", username, rollback_supported=True
            )
        return ConnectorActionResult(
            status="rolled_back",
            capability="identity.local_user.enable",
            target=username,
            message="Simulated local-user compensation; no account was changed.",
            verified=True,
            effective_at=datetime.now(UTC),
            rollback_supported=True,
        )


class WindowsLocalFirewallConnector:
    """Simulation-only placeholder; local firewall mutation is not authorized."""

    async def create_block_rule(
        self, ip_address: str, is_simulation: bool = True
    ) -> ConnectorActionResult:
        if not is_simulation:
            return _live_unavailable(
                "network.local_firewall.rule.create",
                ip_address,
                rollback_supported=True,
            )
        return ConnectorActionResult(
            status="simulated",
            capability="network.local_firewall.rule.create",
            target=ip_address,
            message="Simulated firewall rule creation; no rule was changed.",
            verified=True,
            effective_at=datetime.now(UTC),
            rollback_supported=True,
        )

    async def delete_block_rule(
        self, ip_address: str, is_simulation: bool = True
    ) -> ConnectorActionResult:
        if not is_simulation:
            return _live_unavailable(
                "network.local_firewall.rule.delete",
                ip_address,
                rollback_supported=True,
            )
        return ConnectorActionResult(
            status="rolled_back",
            capability="network.local_firewall.rule.delete",
            target=ip_address,
            message="Simulated firewall compensation; no rule was changed.",
            verified=True,
            effective_at=datetime.now(UTC),
            rollback_supported=True,
        )
