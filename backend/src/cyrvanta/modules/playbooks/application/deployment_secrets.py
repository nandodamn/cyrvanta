from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DeploymentSecretMetadata:
    purpose: str
    present: bool
    version: int
    rotated_at: datetime | None


class DeploymentSecretLease(Protocol):
    def consume(self, consumer: str) -> str: ...


class DeploymentSecretStorePort(Protocol):
    def lease(self, purpose: str, consumer: str) -> DeploymentSecretLease: ...

    def metadata(self, purpose: str) -> DeploymentSecretMetadata: ...
