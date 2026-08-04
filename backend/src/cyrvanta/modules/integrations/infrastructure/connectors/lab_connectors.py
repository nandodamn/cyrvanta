import logging
import subprocess
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


class SmtpLabConnector:
    """Laboratory SMTP connector capturing emails without external internet transmission."""

    def __init__(self, host: str = "127.0.0.1", port: int = 1025) -> None:
        self.host = host
        self.port = port

    async def send_email(self, recipient: str, subject: str, body: str) -> ConnectorActionResult:
        now = datetime.now(UTC)
        logger.info("[SMTP-LAB] Captured email to %s with subject: %s", recipient, subject)
        return ConnectorActionResult(
            status="simulated",
            capability="notification.email.send",
            target=recipient,
            message=f"Captured test email to {recipient} (Subject: {subject})",
            verified=True,
            effective_at=now,
            rollback_supported=False,
        )


class WindowsLocalUserConnector:
    """Laboratory Windows local user connector for account isolation testing."""

    async def disable_user(self, username: str, is_simulation: bool = True) -> ConnectorActionResult:
        now = datetime.now(UTC)
        if is_simulation or username in ("Administrator", "System", "guest"):
            return ConnectorActionResult(
                status="simulated",
                capability="identity.local_user.disable",
                target=username,
                message=f"[SIMULATION] Windows local user '{username}' marked disabled for lab testing.",
                verified=True,
                effective_at=now,
                rollback_supported=True,
            )

        try:
            cmd = ["net", "user", username, "/active:no"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return ConnectorActionResult(
                    status="succeeded",
                    capability="identity.local_user.disable",
                    target=username,
                    message=f"Successfully disabled Windows local account '{username}'.",
                    verified=True,
                    effective_at=now,
                    rollback_supported=True,
                )
            return ConnectorActionResult(
                status="failed",
                capability="identity.local_user.disable",
                target=username,
                message=f"Failed to disable user: {res.stderr.strip()}",
                verified=False,
                effective_at=now,
                rollback_supported=True,
            )
        except Exception as exc:  # noqa: BLE001
            return ConnectorActionResult(
                status="failed",
                capability="identity.local_user.disable",
                target=username,
                message=str(exc),
                verified=False,
                effective_at=now,
                rollback_supported=True,
            )

    async def enable_user(self, username: str, is_simulation: bool = True) -> ConnectorActionResult:
        now = datetime.now(UTC)
        if is_simulation:
            return ConnectorActionResult(
                status="rolled_back",
                capability="identity.local_user.enable",
                target=username,
                message=f"[SIMULATION] Windows local user '{username}' re-enabled via rollback.",
                verified=True,
                effective_at=now,
                rollback_supported=True,
            )
        try:
            cmd = ["net", "user", username, "/active:yes"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return ConnectorActionResult(
                status="rolled_back" if res.returncode == 0 else "failed",
                capability="identity.local_user.enable",
                target=username,
                message=f"Rollback enable user result: {res.stdout or res.stderr}",
                verified=res.returncode == 0,
                effective_at=now,
                rollback_supported=True,
            )
        except Exception as exc:  # noqa: BLE001
            return ConnectorActionResult(
                status="failed",
                capability="identity.local_user.enable",
                target=username,
                message=str(exc),
                verified=False,
                effective_at=now,
                rollback_supported=True,
            )


class WindowsLocalFirewallConnector:
    """Laboratory Windows local firewall connector for network isolation testing."""

    async def create_block_rule(self, ip_address: str, is_simulation: bool = True) -> ConnectorActionResult:
        now = datetime.now(UTC)
        rule_name = f"Cyrvanta_Block_Lab_{ip_address}"
        if is_simulation or ip_address in ("127.0.0.1", "::1"):
            return ConnectorActionResult(
                status="simulated",
                capability="network.local_firewall.rule.create",
                target=ip_address,
                message=f"[SIMULATION] Local firewall block rule '{rule_name}' staged.",
                verified=True,
                effective_at=now,
                rollback_supported=True,
            )

        try:
            cmd = [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={rule_name}", "dir=in", "action=block", f"remoteip={ip_address}"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            status: Literal["succeeded", "simulated", "failed", "rolled_back"] = "succeeded" if res.returncode == 0 else "failed"
            return ConnectorActionResult(
                status=status,
                capability="network.local_firewall.rule.create",
                target=ip_address,
                message=f"Created firewall block rule for {ip_address}",
                verified=res.returncode == 0,
                effective_at=now,
                rollback_supported=True,
            )
        except Exception as exc:  # noqa: BLE001
            return ConnectorActionResult(
                status="failed",
                capability="network.local_firewall.rule.create",
                target=ip_address,
                message=str(exc),
                verified=False,
                effective_at=now,
                rollback_supported=True,
            )

    async def delete_block_rule(self, ip_address: str, is_simulation: bool = True) -> ConnectorActionResult:
        now = datetime.now(UTC)
        rule_name = f"Cyrvanta_Block_Lab_{ip_address}"
        if is_simulation:
            return ConnectorActionResult(
                status="rolled_back",
                capability="network.local_firewall.rule.delete",
                target=ip_address,
                message=f"[SIMULATION] Firewall block rule '{rule_name}' removed via rollback.",
                verified=True,
                effective_at=now,
                rollback_supported=True,
            )

        try:
            cmd = ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            status: Literal["succeeded", "simulated", "failed", "rolled_back"] = "rolled_back" if res.returncode == 0 else "failed"
            return ConnectorActionResult(
                status=status,
                capability="network.local_firewall.rule.delete",
                target=ip_address,
                message=f"Deleted firewall block rule for {ip_address}",
                verified=res.returncode == 0,
                effective_at=now,
                rollback_supported=True,
            )
        except Exception as exc:  # noqa: BLE001
            return ConnectorActionResult(
                status="failed",
                capability="network.local_firewall.rule.delete",
                target=ip_address,
                message=str(exc),
                verified=False,
                effective_at=now,
                rollback_supported=True,
            )
