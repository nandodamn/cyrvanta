from urllib.parse import urlsplit
from uuid import UUID

from cyrvanta.modules.integrations.application.connection_service import (
    IntegrationConfigurationError,
    IntegrationConnectionService,
)
from cyrvanta.modules.integrations.application.ports.siem_connector import (
    SIEMConnectorPort,
)
from cyrvanta.modules.integrations.domain.models import ConnectorConfiguration
from cyrvanta.modules.integrations.infrastructure.registry.connector_registry import (
    ConnectorRegistry,
)
from cyrvanta.modules.integrations.infrastructure.wazuh.adapter import WazuhSIEMAdapter
from cyrvanta.modules.integrations.infrastructure.wazuh.config import (
    WazuhConnectorConfigV1,
)
from cyrvanta.shared.coercion import as_float
from cyrvanta.shared.config import get_settings


def _wazuh_factory(configuration: ConnectorConfiguration) -> SIEMConnectorPort:
    return WazuhSIEMAdapter(
        WazuhConnectorConfigV1.model_validate(configuration.values),
        source_instance_id=configuration.integration_id,
    )


def production_connector_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register("wazuh", _wazuh_factory)
    return registry


async def configured_wazuh_connection(
    tenant_id: UUID,
) -> tuple[UUID, SIEMConnectorPort]:
    settings = get_settings()
    if settings.wazuh_mode != "live" or settings.opensearch_mode != "live":
        raise IntegrationConfigurationError("INTEGRATION_DISABLED")
    connections = IntegrationConnectionService(settings)
    manager = await connections.resolve_single_connector(tenant_id, "WAZUH")
    indexer = await connections.resolve_single_connector(tenant_id, "OPENSEARCH")
    manager_url = urlsplit(str(manager.values["base_url"]))
    indexer_url = urlsplit(str(indexer.values["base_url"]))
    if manager_url.hostname is None or indexer_url.hostname is None:
        raise IntegrationConfigurationError("INTEGRATION_CONFIGURATION_INVALID")
    integration_id = UUID(manager.reference)
    configuration = WazuhConnectorConfigV1(
        manager_host=manager_url.hostname,
        manager_port=manager_url.port or (443 if manager_url.scheme == "https" else 80),
        indexer_url=str(indexer.values["base_url"]),
        index_pattern=settings.opensearch_index_pattern,
        verify_tls=indexer_url.scheme == "https",
        timeout_seconds=min(
            as_float(manager.values.get("timeout_seconds"), 10),
            as_float(indexer.values.get("timeout_seconds"), 10),
        ),
    )
    connector = WazuhSIEMAdapter(
        configuration,
        source_instance_id=integration_id,
        indexer_username=(
            str(indexer.values["username"]) if indexer.values.get("username") else None
        ),
        indexer_password=(
            str(indexer.values["password"]) if indexer.values.get("password") else None
        ),
        indexer_bearer_token=(
            str(indexer.values["bearer_token"]) if indexer.values.get("bearer_token") else None
        ),
    )
    return integration_id, connector


async def configured_wazuh_connector(tenant_id: UUID) -> SIEMConnectorPort:
    _, connector = await configured_wazuh_connection(tenant_id)
    return connector
