import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cyrvanta.shared.domain.events import (
    COMPONENT_PATTERN,
    EVENT_NAME_PATTERN,
    DomainEvent,
)


class EventEnvelopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_name: str
    schema_version: int = Field(ge=1)
    tenant_id: UUID
    aggregate_type: str
    aggregate_id: UUID
    occurred_at: datetime
    correlation_id: UUID
    causation_id: UUID | None
    producer: str
    payload: dict[str, Any]

    @field_validator("event_name")
    @classmethod
    def valid_event_name(cls, value: str) -> str:
        if EVENT_NAME_PATTERN.fullmatch(value) is None:
            raise ValueError("invalid event name")
        return value

    @field_validator("aggregate_type", "producer")
    @classmethod
    def valid_component(cls, value: str) -> str:
        if COMPONENT_PATTERN.fullmatch(value) is None:
            raise ValueError("invalid component")
        return value

    @field_validator("occurred_at")
    @classmethod
    def aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value.astimezone(UTC)

    @classmethod
    def from_domain(cls, event: DomainEvent) -> "EventEnvelopeV1":
        return cls(
            event_id=event.event_id,
            event_name=event.event_name,
            schema_version=event.schema_version,
            tenant_id=event.tenant_id,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            occurred_at=event.occurred_at,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            producer=event.producer,
            payload=dict(event.payload),
        )

    def to_domain(self) -> DomainEvent:
        return DomainEvent(
            event_id=self.event_id,
            event_name=self.event_name,
            schema_version=self.schema_version,
            tenant_id=self.tenant_id,
            aggregate_type=self.aggregate_type,
            aggregate_id=self.aggregate_id,
            occurred_at=self.occurred_at,
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            producer=self.producer,
            payload=self.payload,
        )

    def payload_size(self) -> int:
        return len(
            json.dumps(
                self.payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )

    def message_body(self) -> bytes:
        return self.model_dump_json().encode("utf-8")
