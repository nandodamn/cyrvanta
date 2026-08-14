from uuid import UUID

import pytest

from cyrvanta.modules.operations.application.topology_service import NetworkTopologyService


@pytest.mark.asyncio
async def test_get_network_topology_returns_security_nodes_and_edges() -> None:
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")

    response = await NetworkTopologyService().get_topology(tenant_id)

    assert response.tenant_id == tenant_id
    assert len(response.nodes) >= 6
    assert len(response.edges) >= 5

    # Core Cyrvanta platform nodes
    core_nodes = [n for n in response.nodes if n.category == "CYRVANTA_CORE"]
    assert len(core_nodes) >= 4
    assert any(n.id == "gw-01" and n.type == "GATEWAY" for n in core_nodes)
    assert any(n.id == "db-01" and n.type == "DATABASE" for n in core_nodes)

    # Security feeds & sensors
    feed_nodes = [n for n in response.nodes if n.category == "SECURITY_FEED"]
    assert any(n.id == "siem-01" and n.type == "SIEM" for n in feed_nodes)

    # Monitored tenant assets (consolidated host with multiple IPs & services)
    asset_nodes = [n for n in response.nodes if n.category == "MONITORED_ASSET"]
    assert len(asset_nodes) >= 2
    lab_srv = next((n for n in asset_nodes if n.id == "lab-server-01"), None)
    assert lab_srv is not None
    assert len(lab_srv.ip_addresses) >= 2
    assert len(lab_srv.services) >= 2
    assert any(s.port == 443 for s in lab_srv.services)
    assert any(s.port == 8080 for s in lab_srv.services)

    assert response.updated_at
