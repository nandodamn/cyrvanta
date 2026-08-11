from uuid import UUID

import pytest

from cyrvanta.modules.operations.application.topology_service import NetworkTopologyService


@pytest.mark.asyncio
async def test_get_network_topology_is_explicitly_empty_without_inventory() -> None:
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")

    response = await NetworkTopologyService().get_topology(tenant_id)

    assert response.tenant_id == tenant_id
    assert response.nodes == []
    assert response.edges == []
    assert response.updated_at
