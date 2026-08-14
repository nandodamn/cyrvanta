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
        # Readiness reporting and the automatic Wazuh binding both decide whether
        # a credential may back a real action, so both must gate on the version.
        PlaybookAdministrationService._native_action_blockers,
        PlaybookAdministrationService._bind_wazuh_actions,
        NativePlaybookDispatcher._validate_action_bindings,
    )

    for guarded_path in guarded_paths:
        source = inspect.getsource(guarded_path)
        # The guard may be expressed as a SQL filter on IntegrationModel or as a
        # comparison on the loaded row (which lets a caller report *why* a
        # credential is unusable), but it must always be present.
        assert "configuration_schema_version" in source, guarded_path.__qualname__
        assert "CURRENT_CONFIGURATION_SCHEMA_VERSION" in source, guarded_path.__qualname__
