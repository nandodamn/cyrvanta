import inspect

from cyrvanta.modules.integrations.application.resolver import ConnectionResolver
from cyrvanta.modules.playbooks.application.administration_service import (
    PlaybookAdministrationService,
)
from cyrvanta.modules.playbooks.infrastructure.native_engine import NativePlaybookDispatcher


def test_current_connection_validation_version_gates_every_readiness_path() -> None:
    guarded_paths = (
        ConnectionResolver.resolve,
        PlaybookAdministrationService.validate_connection_dependencies,
        PlaybookAdministrationService.create_action_binding,
        PlaybookAdministrationService.verify_action_binding,
        PlaybookAdministrationService._native_actions_ready,
        NativePlaybookDispatcher._validate_action_bindings,
    )

    for guarded_path in guarded_paths:
        source = inspect.getsource(guarded_path)
        assert "IntegrationModel.configuration_schema_version" in source
        assert "CURRENT_CONFIGURATION_SCHEMA_VERSION" in source
