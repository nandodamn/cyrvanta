from pathlib import Path

import pytest

from cyrvanta.modules.integrations.infrastructure.connectors.enterprise_connectors import (
    CrowdStrikeFalconConnector,
    DefenderEndpointConnector,
    FortinetFirewallConnector,
    PaloAltoFirewallConnector,
)
from cyrvanta.modules.integrations.infrastructure.connectors.lab_connectors import (
    WindowsLocalFirewallConnector,
    WindowsLocalUserConnector,
)


@pytest.mark.asyncio
async def test_lab_connectors_reject_non_simulated_mutations() -> None:
    user = WindowsLocalUserConnector()
    firewall = WindowsLocalFirewallConnector()
    results = [
        await user.disable_user("lab-user", is_simulation=False),
        await user.enable_user("lab-user", is_simulation=False),
        await firewall.create_block_rule("192.0.2.10", is_simulation=False),
        await firewall.delete_block_rule("192.0.2.10", is_simulation=False),
    ]

    assert all(result.status == "failed" for result in results)
    assert all(result.verified is False for result in results)
    assert all(result.message == "LIVE_CONNECTOR_NOT_AVAILABLE" for result in results)


@pytest.mark.asyncio
async def test_enterprise_placeholders_reject_non_simulated_mutations() -> None:
    results = [
        await DefenderEndpointConnector().isolate_host("device-1", is_simulation=False),
        await DefenderEndpointConnector().release_host("device-1", is_simulation=False),
        await CrowdStrikeFalconConnector().contain_host("aid-1", is_simulation=False),
        await PaloAltoFirewallConnector().block_ip("192.0.2.10", is_simulation=False),
        await PaloAltoFirewallConnector().unblock_ip("192.0.2.10", is_simulation=False),
        await FortinetFirewallConnector().block_ip("192.0.2.10", is_simulation=False),
    ]

    assert all(result.status == "failed" for result in results)
    assert all(result.verified is False for result in results)
    assert all(result.message == "LIVE_CONNECTOR_NOT_AVAILABLE" for result in results)


def test_connector_modules_contain_no_local_process_execution() -> None:
    connector_root = (
        Path(__file__).parents[2]
        / "src"
        / "cyrvanta"
        / "modules"
        / "integrations"
        / "infrastructure"
        / "connectors"
    )
    lab_source = (connector_root / "lab_connectors.py").read_text(encoding="utf-8")
    enterprise_source = (connector_root / "enterprise_connectors.py").read_text(
        encoding="utf-8"
    )

    assert "subprocess" not in lab_source
    assert 'status="succeeded"' not in lab_source
    assert 'status="succeeded"' not in enterprise_source
    assert "recipient, subject" not in lab_source
