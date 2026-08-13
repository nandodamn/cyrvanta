from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cyrvanta.modules.integrations.application import connection_service as connection_module
from cyrvanta.modules.integrations.application.connection_service import (
    CURRENT_CONFIGURATION_SCHEMA_VERSION,
    IntegrationConfigurationError,
    IntegrationConnectionService,
)


def service(environment: str = "production") -> IntegrationConnectionService:
    instance = object.__new__(IntegrationConnectionService)
    instance.settings = SimpleNamespace(environment=environment)
    return instance


def test_smtp_configuration_is_typed_and_transport_safe() -> None:
    validator = service()
    validator._validate(
        "SMTP",
        {
            "host": "smtp.example.test",
            "port": 587,
            "from_address": "cyrvanta@example.test",
            "username": "service-account",
            "password": "test-password",
            "use_starttls": True,
        },
    )

    invalid = (
        {
            "host": "smtp.example.test",
            "port": 587,
            "from_address": "invalid",
        },
        {
            "host": "smtp.example.test",
            "port": 587,
            "from_address": "cyrvanta@example.test",
            "username": "service-account",
        },
        {
            "host": "smtp.example.test",
            "port": 587,
            "from_address": "cyrvanta@example.test",
            "use_starttls": "true",
        },
        {
            "host": "smtp.example.test",
            "port": 587,
            "from_address": "cyrvanta@example.test",
            "bearer_token": "ignored-secret",
        },
    )
    for configuration in invalid:
        with pytest.raises(
            IntegrationConfigurationError,
            match="INTEGRATION_CONFIGURATION_INVALID",
        ):
            validator._validate("SMTP", configuration)


def test_non_loopback_production_connections_require_https() -> None:
    with pytest.raises(IntegrationConfigurationError, match="INTEGRATION_TLS_REQUIRED"):
        service()._validate("HTTP_ALLOWLISTED", {"base_url": "http://tickets.example.test"})

    service()._validate("HTTP_ALLOWLISTED", {"base_url": "http://localhost:8081"})


@pytest.mark.parametrize(
    "configuration",
    [
        {"base_url": "https://user:password@tickets.example.test"},
        {"base_url": "https://tickets.example.test?tenant=other"},
        {"base_url": "https://tickets.example.test#fragment"},
        {
            "base_url": "https://tickets.example.test",
            "api_key": "first-token",
            "bearer_token": "second-token",
        },
    ],
)
def test_http_allowlist_rejects_ambiguous_origin_or_authentication(
    configuration: dict[str, object],
) -> None:
    with pytest.raises(
        IntegrationConfigurationError,
        match="INTEGRATION_CONFIGURATION_INVALID",
    ):
        service()._validate("HTTP_ALLOWLISTED", configuration)


def test_connector_rejects_fields_it_will_not_consume() -> None:
    with pytest.raises(
        IntegrationConfigurationError,
        match="INTEGRATION_CONFIGURATION_INVALID",
    ):
        service()._validate(
            "N8N",
            {
                "base_url": "https://n8n.example.test",
                "api_key": "test-api-key",
                "bearer_token": "ignored-token",
            },
        )


@pytest.mark.asyncio
async def test_legacy_invalid_connection_cannot_resolve_for_playbook(monkeypatch) -> None:
    tenant_id, connection_id = uuid4(), uuid4()
    row = SimpleNamespace(id=connection_id, connector_type="HTTP_ALLOWLISTED")
    session = SimpleNamespace(scalar=AsyncMock(return_value=row))

    @asynccontextmanager
    async def session_scope(scoped_tenant_id):
        assert scoped_tenant_id == tenant_id
        yield session

    validator = service()
    validator._decrypt = lambda _row: {"base_url": "https://tickets.example.test?legacy=true"}
    monkeypatch.setattr(connection_module, "tenant_session", session_scope)

    with pytest.raises(
        IntegrationConfigurationError,
        match="PLAYBOOK_CREDENTIAL_UNAVAILABLE",
    ):
        await validator.resolve_credential(tenant_id, str(connection_id))


@pytest.mark.asyncio
async def test_legacy_invalid_single_connector_is_unavailable(monkeypatch) -> None:
    tenant_id, connection_id = uuid4(), uuid4()
    row = SimpleNamespace(id=connection_id, connector_type="OPENSEARCH")
    scalar_result = SimpleNamespace(all=lambda: [row])
    session = SimpleNamespace(scalars=AsyncMock(return_value=scalar_result))

    @asynccontextmanager
    async def session_scope(scoped_tenant_id):
        assert scoped_tenant_id == tenant_id
        yield session

    validator = service()
    validator._decrypt = lambda _row: {"base_url": "https://user:password@search.example.test"}
    monkeypatch.setattr(connection_module, "tenant_session", session_scope)

    with pytest.raises(
        IntegrationConfigurationError,
        match="INTEGRATION_CONNECTION_UNAVAILABLE",
    ):
        await validator.resolve_single_connector(tenant_id, "OPENSEARCH")


@pytest.mark.asyncio
async def test_probe_rejects_legacy_invalid_configuration_without_network(monkeypatch) -> None:
    tenant_id, actor_id, connection_id, correlation_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    row = SimpleNamespace(
        id=connection_id,
        connector_type="HTTP_ALLOWLISTED",
        status="active",
        last_health_check_at=None,
        last_error_code=None,
        last_successful_sync_at=None,
    )
    session = SimpleNamespace(scalar=AsyncMock(return_value=row), add=lambda _item: None)

    @asynccontextmanager
    async def session_scope(scoped_tenant_id):
        assert scoped_tenant_id == tenant_id
        yield session

    validator = service()
    validator._decrypt = lambda _row: {"base_url": "https://tickets.example.test#legacy"}
    validator._probe = AsyncMock()
    monkeypatch.setattr(connection_module, "tenant_session", session_scope)

    result = await validator.probe(
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        connection_id=connection_id,
        correlation_id=correlation_id,
    )

    assert result.healthy is False
    assert result.error_code == "INTEGRATION_CONFIGURATION_INVALID"
    assert row.status == "unhealthy"
    validator._probe.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_probe_upgrades_configuration_validation_version(monkeypatch) -> None:
    tenant_id, actor_id, connection_id, correlation_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    row = SimpleNamespace(
        id=connection_id,
        connector_type="HTTP_ALLOWLISTED",
        configuration_schema_version="1.0",
        status="active",
        last_health_check_at=None,
        last_error_code=None,
        last_successful_sync_at=None,
    )
    session = SimpleNamespace(scalar=AsyncMock(return_value=row), add=lambda _item: None)

    @asynccontextmanager
    async def session_scope(scoped_tenant_id):
        assert scoped_tenant_id == tenant_id
        yield session

    validator = service()
    validator._decrypt = lambda _row: {"base_url": "https://tickets.example.test"}
    validator._probe = AsyncMock(return_value=(True, None))
    monkeypatch.setattr(connection_module, "tenant_session", session_scope)

    result = await validator.probe(
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        connection_id=connection_id,
        correlation_id=correlation_id,
    )

    assert result.healthy is True
    assert row.status == "active"
    assert row.configuration_schema_version == CURRENT_CONFIGURATION_SCHEMA_VERSION
    validator._probe.assert_awaited_once()
