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
    assert any(n.id == "gw-01" and n.type == "GATEWAY" for n in response.nodes)
    assert any(n.id == "siem-01" and n.type == "SIEM" for n in response.nodes)
    assert any(n.id == "db-01" and n.type == "DATABASE" for n in response.nodes)
    assert response.updated_at
