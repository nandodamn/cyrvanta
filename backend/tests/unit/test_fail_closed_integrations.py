from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest

from cyrvanta.modules.integrations.application import resolver as resolver_module
from cyrvanta.modules.integrations.application.resolver import ConnectionResolver

TENANT_ID = UUID("e18357f0-2075-462b-a0ea-b1eaa1ffb5ec")


class _ScalarResult:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return self._items


class _Session:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    async def scalars(self, _statement: object) -> _ScalarResult:
        return _ScalarResult(self._items)


def _tenant_session(items: list[object]):
    @asynccontextmanager
    async def session(_tenant_id: UUID):
        yield _Session(items)

    return session


@pytest.mark.asyncio
async def test_unknown_capability_fails_closed_without_database_access() -> None:
    result = await ConnectionResolver().resolve(TENANT_ID, "unknown.capability")

    assert result.resolution_status == "not_resolved"
    assert result.connection_id is None
    assert result.selection_reason == "capability_not_registered"
    assert result.blocking is True
    assert result.simulation_supported is False


@pytest.mark.asyncio
async def test_missing_tenant_connection_has_no_fallback(monkeypatch) -> None:
    monkeypatch.setattr(resolver_module, "tenant_session", _tenant_session([]))

    result = await ConnectionResolver().resolve(TENANT_ID, "findings.ingest")

    assert result.resolution_status == "not_resolved"
    assert result.connection_id is None
    assert result.selection_reason == "tenant_connection_unavailable"
    assert result.blocking is True
    assert result.simulation_supported is False


@pytest.mark.asyncio
async def test_active_verified_tenant_connection_is_resolved(monkeypatch) -> None:
    integration = SimpleNamespace(
        id=UUID("8dd28ee8-fe32-43bb-87ef-04e63446d1e2"),
        connector_type="WAZUH",
        capabilities_snapshot={"capabilities": ["findings.ingest"]},
    )
    monkeypatch.setattr(resolver_module, "tenant_session", _tenant_session([integration]))

    result = await ConnectionResolver().resolve(TENANT_ID, "findings.ingest")

    assert result.resolution_status == "resolved"
    assert result.connection_id == str(integration.id)
    assert result.selection_reason == "tenant_healthy_verified_connection"
    assert result.simulation_supported is False
    assert result.blocking is False