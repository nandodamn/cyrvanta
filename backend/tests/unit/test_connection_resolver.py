from uuid import UUID

import pytest

from cyrvanta.modules.integrations.application.resolver import ConnectionResolver


@pytest.mark.asyncio
async def test_connection_resolver_rejects_unknown_capability():
    tenant_id = UUID("e18357f0-2075-462b-a0ea-b1eaa1ffb5ec")
    resolver = ConnectionResolver()

    result = await resolver.resolve(tenant_id, "not.registered")
    assert result.resolution_status == "not_resolved"
    assert result.connector_type is None
    assert result.connection_id is None
    assert result.blocking is True
