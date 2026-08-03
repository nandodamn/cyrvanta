from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass

from cyrvanta.modules.playbooks.application.deployment_secrets import (
    DeploymentSecretMetadata,
)

ALLOWED_PURPOSES = {"n8n-dispatch", "n8n-callback"}


@dataclass(slots=True)
class OneUseSecretLease:
    _value: str | None
    _consumer: str

    def consume(self, consumer: str) -> str:
        if consumer != self._consumer or self._value is None:
            raise PermissionError("deployment secret lease is unavailable")
        value = self._value
        self._value = None
        return value


class DerivedDeploymentSecretStore:
    """Derive purpose-separated internal keys from an external installation key."""

    def __init__(self, master_key: str, version: int) -> None:
        if version < 1:
            raise ValueError("secret version must be positive")
        try:
            decoded = base64.urlsafe_b64decode(master_key.encode())
        except ValueError as exc:
            raise ValueError("installation master key is invalid") from exc
        if len(decoded) != 32:
            raise ValueError("installation master key must contain 32 bytes")
        self._master = decoded
        self._version = version

    def lease(self, purpose: str, consumer: str) -> OneUseSecretLease:
        if purpose not in ALLOWED_PURPOSES or consumer != "n8n-adapter":
            raise PermissionError("deployment secret purpose or consumer is denied")
        material = f"cyrvanta:{purpose}:v{self._version}".encode()
        value = base64.urlsafe_b64encode(
            hmac.new(self._master, material, hashlib.sha256).digest()
        ).decode()
        return OneUseSecretLease(value, consumer)

    def metadata(self, purpose: str) -> DeploymentSecretMetadata:
        if purpose not in ALLOWED_PURPOSES:
            raise PermissionError("deployment secret purpose is denied")
        return DeploymentSecretMetadata(
            purpose=purpose,
            present=True,
            version=self._version,
            rotated_at=None,
        )


def resolve_internal_secret(
    *, master_key: str, version: int, purpose: str, explicit_value: str
) -> str:
    if explicit_value:
        return explicit_value
    return (
        DerivedDeploymentSecretStore(master_key, version)
        .lease(purpose, "n8n-adapter")
        .consume("n8n-adapter")
    )
