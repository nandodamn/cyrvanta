from uuid import NAMESPACE_URL, UUID, uuid5

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


def configured_wazuh_integration_id(tenant_id: UUID) -> UUID:
    return uuid5(NAMESPACE_URL, f"cyrvanta:{tenant_id}:wazuh-local")


def configured_wazuh_connector(tenant_id: UUID) -> SIEMConnectorPort:
    settings = get_settings()
    integration_id = configured_wazuh_integration_id(tenant_id)
    configuration = ConnectorConfiguration(
        integration_id=integration_id,
        tenant_id=tenant_id,
        connector_type="wazuh",
        schema_version="1",
        values={
            "manager_host": settings.wazuh_manager_host,
            "manager_port": settings.wazuh_manager_port,
            "indexer_url": settings.opensearch_url,
            "index_pattern": settings.opensearch_index_pattern,
            "verify_tls": settings.opensearch_url.startswith("https://"),
        },
    )
    return production_connector_registry().create("wazuh", configuration)
