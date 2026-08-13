from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EngineContext:
    tenant_id: UUID
    correlation_id: UUID
    causation_id: UUID | None
    deadline: datetime


@dataclass(frozen=True, slots=True)
class EngineValidationResult:
    valid: bool
    digest: str | None = None
    error_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EngineDryRunResult:
    valid: bool
    engine_type: str
    steps: tuple[str, ...]
    error_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EngineDispatchReceipt:
    accepted: bool
    engine_type: str
    execution_reference: str | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class EngineHealthResult:
    healthy: bool
    engine_type: str
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class EngineVersion:
    id: UUID
    artifact_sha256: str
    artifact: dict[str, object] | None
    status: str


@dataclass(frozen=True, slots=True)
class EngineBinding:
    id: UUID
    engine_type: str
    desired_digest: str
    observed_digest: str | None
    sync_status: str
    active: bool


@dataclass(frozen=True, slots=True)
class EngineExecution:
    id: UUID
    playbook_version_id: UUID
    binding_id: UUID
    execution_mode: str
    inputs: dict[str, object]


class PlaybookEnginePort(Protocol):
    async def validate(
        self, context: EngineContext, version: EngineVersion, binding: EngineBinding
    ) -> EngineValidationResult: ...

    async def dry_run(
        self,
        context: EngineContext,
        version: EngineVersion,
        binding: EngineBinding,
        inputs: dict[str, object],
    ) -> EngineDryRunResult: ...

    async def dispatch(
        self, context: EngineContext, execution: EngineExecution
    ) -> EngineDispatchReceipt: ...

    async def health(
        self, context: EngineContext, binding: EngineBinding
    ) -> EngineHealthResult: ...


@dataclass(frozen=True, slots=True)
class ActionDescriptor:
    code: str
    version: str
    modes: tuple[str, ...]
    impact: str
    timeout_seconds: int
    retry_safe: bool
    cancellable: bool
    egress: str
    sensitive_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    error_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProbeResult:
    healthy: bool
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class ActionResult:
    succeeded: bool
    output: dict[str, object]
    error_code: str | None = None
    safe_detail: str | None = None


class CredentialHandle(Protocol):
    @property
    def reference(self) -> str: ...


class ActionConnectorPort(Protocol):
    def describe(self) -> ActionDescriptor: ...

    def validate_configuration(self, configuration: dict[str, object]) -> ValidationResult: ...

    async def probe(
        self, context: EngineContext, configuration: dict[str, object]
    ) -> ProbeResult: ...

    async def execute(
        self,
        context: EngineContext,
        action_input: dict[str, object],
        configuration: dict[str, object],
        idempotency_key: str,
        credential_handle: CredentialHandle | None,
    ) -> ActionResult: ...


class CredentialResolverPort(Protocol):
    async def resolve(
        self, tenant_id: UUID, alias: str, purpose: str, action_code: str
    ) -> CredentialHandle: ...
