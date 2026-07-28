from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

EVENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)+$")
COMPONENT_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,119}$")


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: UUID
    event_name: str
    schema_version: int
    tenant_id: UUID
    aggregate_type: str
    aggregate_id: UUID
    occurred_at: datetime
    correlation_id: UUID
    causation_id: UUID | None
    producer: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if EVENT_NAME_PATTERN.fullmatch(self.event_name) is None:
            raise ValueError("event_name must be a lowercase dotted code")
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        if COMPONENT_PATTERN.fullmatch(self.aggregate_type) is None:
            raise ValueError("aggregate_type is invalid")
        if COMPONENT_PATTERN.fullmatch(self.producer) is None:
            raise ValueError("producer is invalid")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(UTC))
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    @classmethod
    def create(
        cls,
        *,
        event_name: str,
        tenant_id: UUID,
        aggregate_type: str,
        aggregate_id: UUID,
        correlation_id: UUID,
        producer: str,
        payload: Mapping[str, Any],
        causation_id: UUID | None = None,
        schema_version: int = 1,
        occurred_at: datetime | None = None,
    ) -> DomainEvent:
        return cls(
            event_id=uuid4(),
            event_name=event_name,
            schema_version=schema_version,
            tenant_id=tenant_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            occurred_at=occurred_at or datetime.now(UTC),
            correlation_id=correlation_id,
            causation_id=causation_id,
            producer=producer,
            payload=payload,
        )

    def create_child(
        self,
        *,
        event_name: str,
        aggregate_type: str,
        aggregate_id: UUID,
        producer: str,
        payload: Mapping[str, Any],
        schema_version: int = 1,
    ) -> DomainEvent:
        return self.create(
            event_name=event_name,
            tenant_id=self.tenant_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            correlation_id=self.correlation_id,
            causation_id=self.event_id,
            producer=producer,
            payload=payload,
            schema_version=schema_version,
        )
