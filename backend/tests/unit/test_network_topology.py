import re
from uuid import UUID

import pytest

from cyrvanta.modules.operations.application.topology_service import (
    NetworkTopologyService,
    _subnet_of,
)
from cyrvanta.shared.database import SessionFactory
from sqlalchemy import text


async def _existing_tenant_id() -> UUID:
    async with SessionFactory() as session, session.begin():
        await session.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
        return (await session.execute(text("SELECT id FROM tenants LIMIT 1"))).scalar()


@pytest.mark.asyncio
async def test_topology_reports_only_probed_cyrvanta_dependencies() -> None:
    """Core nodes must come from this deployment's real configuration and probes."""
    tenant_id = await _existing_tenant_id()

    response = await NetworkTopologyService().get_topology(tenant_id)

    assert response.tenant_id == tenant_id
    core = {node.id: node for node in response.nodes if node.category == "CYRVANTA_CORE"}
    # Postgres, Redis and RabbitMQ are always configured for this backend to run.
    assert {"db-01", "cache-01", "broker-01"} <= set(core)

    for node in core.values():
        # A probed dependency is either reachable with a measured round trip, or
        # explicitly OFFLINE -- never "ONLINE" with an invented latency.
        if node.status == "ONLINE":
            assert node.latency_ms is not None and node.latency_ms > 0
        else:
            assert node.status == "OFFLINE"

    # The three infrastructure dependencies really are reachable from the test
    # container, so their addresses must be genuinely resolved (not placeholders).
    for node_id in ("db-01", "cache-01", "broker-01"):
        node = core[node_id]
        assert node.status == "ONLINE"
        assert re.match(r"^\d{1,3}(\.\d{1,3}){3}$", node.ip_address), node.ip_address
        assert node.subnet.endswith("/24")


@pytest.mark.asyncio
async def test_topology_never_fabricates_lab_hosts_or_addresses() -> None:
    """Regression: the map used to invent hosts, IPs, latency and OS strings."""
    tenant_id = await _existing_tenant_id()

    response = await NetworkTopologyService().get_topology(tenant_id)

    names = {node.name for node in response.nodes}
    assert "SRV-APP-PROD-01 (Application Host)" not in names
    assert "WKSTN-ADMIN-01" not in names
    for node in response.nodes:
        # The old implementation hard-coded a fictional 10.0.x.x plan and even
        # derived addresses from hash(hostname).
        assert not node.ip_address.startswith("10.0.1.")
        assert not node.ip_address.startswith("10.0.2.")
        assert not node.ip_address.startswith("10.0.3.")
        for service in node.services:
            assert service.name not in {
                "Web ERP Portal",
                "Internal API Backend",
                "SSH Management Daemon",
            }

    # Monitored assets are only ever the agents a manager actually reports.
    for node in response.nodes:
        if node.category == "MONITORED_ASSET":
            assert node.id.startswith("agent-")
            assert node.monitored_by, node.name


@pytest.mark.asyncio
async def test_edges_only_connect_nodes_present_in_the_projection() -> None:
    tenant_id = await _existing_tenant_id()

    response = await NetworkTopologyService().get_topology(tenant_id)

    node_ids = {node.id for node in response.nodes}
    for edge in response.edges:
        assert edge.source_id in node_ids
        assert edge.target_id in node_ids


def test_subnet_is_derived_from_a_real_address_or_marked_unresolved() -> None:
    assert _subnet_of("172.18.0.6") == "172.18.0.0/24"
    assert _subnet_of(None) == "unresolved"
    assert _subnet_of("not-an-address") == "unresolved"
