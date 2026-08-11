from uuid import UUID

import pytest

from cyrvanta.modules.integrations.application.resolver import ConnectionResolver

TENANT_ID = UUID("e18357f0-2075-462b-a0ea-b1eaa1ffb5ec")
FUTURE_CAPABILITIES = (
    "identity.local_user.disable",
    "network.local_firewall.rule.create",
    "endpoint.isolate",
    "endpoint.release",
    "network.ip.block",
    "network.ip.unblock",
    "ticket.create",
    "threatintel.indicator.search",
)


@pytest.mark.asyncio
@pytest.mark.parametrize("capability", FUTURE_CAPABILITIES)
async def test_future_capability_is_not_resolvable(capability: str) -> None:
    result = await ConnectionResolver().resolve(TENANT_ID, capability)

    assert result.resolution_status == "not_resolved"
    assert result.connection_id is None
    assert result.connector_type is None
    assert result.selection_reason == "capability_not_registered"
    assert result.simulation_supported is False
    assert result.verification_supported is False
    assert result.blocking is True
