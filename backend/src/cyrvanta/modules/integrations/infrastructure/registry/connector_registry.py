from collections.abc import Callable

from cyrvanta.modules.integrations.application.ports.siem_connector import (
    SIEMConnectorPort,
)
from cyrvanta.modules.integrations.domain.errors import (
    ConnectorError,
    ConnectorErrorCode,
)
from cyrvanta.modules.integrations.domain.models import ConnectorConfiguration

ConnectorFactory = Callable[[ConnectorConfiguration], SIEMConnectorPort]


class ConnectorRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, ConnectorFactory] = {}

    def register(self, connector_type: str, factory: ConnectorFactory) -> None:
        normalized = connector_type.strip().lower()
        if not normalized:
            raise ValueError("Connector type is required")
        if normalized in self._factories:
            raise ValueError(f"Connector type is already registered: {normalized}")
        self._factories[normalized] = factory

    def create(
        self, connector_type: str, configuration: ConnectorConfiguration
    ) -> SIEMConnectorPort:
        normalized = connector_type.strip().lower()
        factory = self._factories.get(normalized)
        if factory is None:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_CONFIGURATION,
                f"Connector type is not registered: {normalized}",
            )
        if configuration.connector_type != normalized:
            raise ConnectorError(
                ConnectorErrorCode.INVALID_CONFIGURATION,
                "Connector configuration type does not match the requested connector",
            )
        return factory(configuration)

    def registered_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

