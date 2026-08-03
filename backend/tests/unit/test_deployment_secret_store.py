import pytest
from cryptography.fernet import Fernet

from cyrvanta.modules.playbooks.infrastructure.deployment_secrets import (
    DerivedDeploymentSecretStore,
)


def test_internal_keys_are_purpose_separated_versioned_and_one_use() -> None:
    master = Fernet.generate_key().decode()
    version_one = DerivedDeploymentSecretStore(master, 1)
    version_two = DerivedDeploymentSecretStore(master, 2)

    dispatch = version_one.lease("n8n-dispatch", "n8n-adapter")
    callback = version_one.lease("n8n-callback", "n8n-adapter")
    dispatch_value = dispatch.consume("n8n-adapter")

    assert dispatch_value != callback.consume("n8n-adapter")
    assert dispatch_value != version_two.lease("n8n-dispatch", "n8n-adapter").consume("n8n-adapter")
    with pytest.raises(PermissionError):
        dispatch.consume("n8n-adapter")


def test_secret_store_denies_unknown_purposes_and_consumers() -> None:
    store = DerivedDeploymentSecretStore(Fernet.generate_key().decode(), 1)

    with pytest.raises(PermissionError):
        store.lease("arbitrary", "n8n-adapter")
    with pytest.raises(PermissionError):
        store.lease("n8n-dispatch", "browser")
