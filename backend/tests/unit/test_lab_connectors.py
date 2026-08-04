import pytest

from cyrvanta.modules.integrations.infrastructure.connectors.lab_connectors import (
    SmtpLabConnector,
    WindowsLocalFirewallConnector,
    WindowsLocalUserConnector,
)


@pytest.mark.asyncio
async def test_smtp_lab_connector():
    connector = SmtpLabConnector()
    res = await connector.send_email(
        recipient="analyst@cyrvanta.uy",
        subject="[ALERT] High Severity Incident Detected",
        body="Action Required: User compromise detected.",
    )
    assert res.status == "simulated"
    assert res.capability == "notification.email.send"
    assert res.verified is True


@pytest.mark.asyncio
async def test_windows_local_user_connector():
    connector = WindowsLocalUserConnector()

    # Simulation disable test
    res = await connector.disable_user("lab_test_user", is_simulation=True)
    assert res.status == "simulated"
    assert res.capability == "identity.local_user.disable"
    assert res.rollback_supported is True

    # Rollback enable test
    res_rollback = await connector.enable_user("lab_test_user", is_simulation=True)
    assert res_rollback.status == "rolled_back"
    assert res_rollback.verified is True


@pytest.mark.asyncio
async def test_windows_local_firewall_connector():
    connector = WindowsLocalFirewallConnector()

    # Simulation block rule test
    res = await connector.create_block_rule("192.168.1.100", is_simulation=True)
    assert res.status == "simulated"
    assert res.capability == "network.local_firewall.rule.create"
    assert res.rollback_supported is True

    # Simulation rollback delete rule test
    res_del = await connector.delete_block_rule("192.168.1.100", is_simulation=True)
    assert res_del.status == "rolled_back"
    assert res_del.verified is True
