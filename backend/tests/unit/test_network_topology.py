from uuid import UUID

import pytest

from cyrvanta.modules.operations.application.topology_service import NetworkTopologyService


@pytest.mark.asyncio
async def test_get_network_topology():
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    service = NetworkTopologyService()
    res = await service.get_topology(tenant_id)

    assert res.tenant_id == tenant_id
    assert len(res.nodes) >= 5
    assert len(res.edges) >= 4

    # Verify key network nodes exist with IP addresses
    node_ips = {node.ip_address for node in res.nodes}
    assert "192.168.1.1" in node_ips
    assert "10.0.4.10" in node_ips
    assert "10.0.4.25" in node_ips
    assert "172.16.0.5" in node_ips
