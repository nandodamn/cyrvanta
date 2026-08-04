from uuid import UUID

import pytest

from cyrvanta.modules.integrations.application.resolver import ConnectionResolver


@pytest.mark.asyncio
async def test_connection_resolver_basic():
    tenant_id = UUID("e18357f0-2075-462b-a0ea-b1eaa1ffb5ec")
    resolver = ConnectionResolver()

    # Test resolving Wazuh alert read
    res1 = await resolver.resolve(tenant_id, "security.alert.read")
    assert res1.resolution_status == "resolved"
    assert res1.connector_type == "wazuh"
    assert res1.requires_approval is False

    # Test resolving Windows Local User disable (requires approval)
    res2 = await resolver.resolve(tenant_id, "identity.local_user.disable")
    assert res2.resolution_status == "resolved"
    assert res2.connector_type == "windows_local"
    assert res2.requires_approval is True
    assert res2.verification_supported is True

    # Test resolving Windows Local Firewall rule create (requires approval)
    res3 = await resolver.resolve(tenant_id, "network.local_firewall.rule.create")
    assert res3.resolution_status == "resolved"
    assert res3.connector_type == "windows_firewall"
    assert res3.requires_approval is True
