from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from cyrvanta.modules.integrations.application import resolver as resolver_module
from cyrvanta.modules.integrations.application.resolver import ConnectionResolver
from cyrvanta.modules.operations.presentation.router import (
    configure_connection,
)
from cyrvanta.modules.operations.presentation.router import (
    test_connection as probe_connection,
)

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
async def test_missing_tenant_connection_has_no_laboratory_fallback(monkeypatch) -> None:
    monkeypatch.setattr(resolver_module, "tenant_session", _tenant_session([]))

    result = await ConnectionResolver().resolve(TENANT_ID, "security.alert.read")

    assert result.resolution_status == "not_resolved"
    assert result.connection_id is None
    assert result.selection_reason == "tenant_connection_unavailable"
    assert result.blocking is True


@pytest.mark.asyncio
async def test_active_tenant_connection_is_resolved(monkeypatch) -> None:
    integration = SimpleNamespace(
        id=UUID("8dd28ee8-fe32-43bb-87ef-04e63446d1e2"),
        connector_type="wazuh",
        capabilities_snapshot={"declared": ["security.alert.read"]},
    )
    monkeypatch.setattr(resolver_module, "tenant_session", _tenant_session([integration]))

    result = await ConnectionResolver().resolve(TENANT_ID, "security.alert.read")

    assert result.resolution_status == "resolved"
    assert result.connection_id == str(integration.id)
    assert result.blocking is False


@pytest.mark.asyncio
async def test_probe_never_returns_synthetic_success() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await probe_connection("wazuh", object())  # type: ignore[arg-type]

    assert exc_info.value.status_code == 501
    assert exc_info.value.detail == "INTEGRATION_PROBE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_configuration_rejects_secret_instead_of_discarding_it() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await configure_connection(
            "n8n",
            {"secret_value": "must-not-be-returned"},
            object(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 501
    assert exc_info.value.detail == "INTEGRATION_CONFIGURATION_UNAVAILABLE"
    assert "must-not-be-returned" not in str(exc_info.value.detail)
