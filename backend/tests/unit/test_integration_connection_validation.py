from types import SimpleNamespace

import pytest

from cyrvanta.modules.integrations.application.connection_service import (
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
