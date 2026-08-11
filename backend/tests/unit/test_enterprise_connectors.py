import pytest

from cyrvanta.modules.integrations.infrastructure.connectors.enterprise_connectors import (
    CrowdStrikeFalconConnector,
    DefenderEndpointConnector,
    MispConnector,
    PaloAltoFirewallConnector,
    ServiceNowConnector,
)


@pytest.mark.asyncio
async def test_defender_endpoint_connector():
    connector = DefenderEndpointConnector()
    res = await connector.isolate_host("device-win-9941", is_simulation=True)
    assert res.status == "simulated"
    assert res.capability == "endpoint.isolate"
    assert res.provider == "Microsoft Defender for Endpoint"
    assert res.rollback_supported is True

    res_rel = await connector.release_host("device-win-9941", is_simulation=True)
    assert res_rel.status == "rolled_back"
    assert res_rel.verified is True


@pytest.mark.asyncio
async def test_crowdstrike_falcon_connector():
    connector = CrowdStrikeFalconConnector()
    res = await connector.contain_host("aid-8812-falcon", is_simulation=True)
    assert res.status == "simulated"
    assert res.capability == "endpoint.isolate"


@pytest.mark.asyncio
async def test_palo_alto_firewall_connector():
    connector = PaloAltoFirewallConnector()
    res = await connector.block_ip("203.0.113.50", is_simulation=True)
    assert res.status == "simulated"
    assert res.capability == "network.ip.block"
    assert res.provider == "Palo Alto PA-3200"

    res_unblock = await connector.unblock_ip("203.0.113.50", is_simulation=True)
    assert res_unblock.status == "rolled_back"


@pytest.mark.asyncio
async def test_servicenow_connector():
    connector = ServiceNowConnector()
    res = await connector.create_incident_ticket(
        "Suspicious Login Alert", "Multiple failed logins from 203.0.113.50"
    )
    assert res.status == "simulated"
    assert res.capability == "ticket.create"
    assert res.provider == "ServiceNow ITSM"


@pytest.mark.asyncio
async def test_misp_connector():
    connector = MispConnector()
    res = await connector.search_indicator("203.0.113.50")
    assert res.status == "simulated"
    assert res.capability == "threatintel.indicator.search"
    assert res.provider == "MISP Threat Intel"
