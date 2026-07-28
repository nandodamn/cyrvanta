from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cyrvanta.shared.config import Settings
from cyrvanta.shared.domain.events import DomainEvent
from cyrvanta.shared.infrastructure.event_envelope import EventEnvelopeV1
from cyrvanta.shared.infrastructure.event_store import SqlEventStore
from cyrvanta.shared.infrastructure.rabbitmq import (
    EventConsumer,
    RabbitTopology,
    persistent_message,
)


def event(**overrides: object) -> DomainEvent:
    values: dict[str, object] = {
        "event_name": "platform.traceability.probe.created",
        "tenant_id": uuid4(),
        "aggregate_type": "traceability_probe",
        "aggregate_id": uuid4(),
        "correlation_id": uuid4(),
        "producer": "cyrvanta.tests",
        "payload": {"synthetic": True},
        "occurred_at": datetime.now(UTC),
    }
    values.update(overrides)
    return DomainEvent.create(**values)  # type: ignore[arg-type]


def test_domain_event_requires_stable_codes_and_utc() -> None:
    with pytest.raises(ValueError, match="event_name"):
        event(event_name="Invalid Event")
    with pytest.raises(ValueError, match="timezone-aware"):
        event(occurred_at=datetime.now())


def test_child_event_preserves_tenant_correlation_and_causation() -> None:
    parent = event()
    child = parent.create_child(
        event_name="platform.traceability.probe.completed",
        aggregate_type="traceability_probe",
        aggregate_id=parent.aggregate_id,
        producer="cyrvanta.tests",
        payload={"synthetic": True},
    )
    assert child.tenant_id == parent.tenant_id
    assert child.correlation_id == parent.correlation_id
    assert child.causation_id == parent.event_id


def test_envelope_round_trip_is_strict_and_preserves_identity() -> None:
    source = event()
    envelope = EventEnvelopeV1.from_domain(source)
    restored = EventEnvelopeV1.model_validate_json(envelope.message_body()).to_domain()
    assert restored == source
    with pytest.raises(ValidationError):
        EventEnvelopeV1.model_validate({**envelope.model_dump(), "unexpected": True})


async def test_payload_limit_fails_before_database_write() -> None:
    session = AsyncMock()
    store = SqlEventStore(AsyncMock(), max_payload_bytes=20)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="configured maximum"):
        await store.add(session, event(payload={"value": "x" * 100}))
    session.execute.assert_not_awaited()


def test_persistent_message_duplicates_envelope_metadata() -> None:
    envelope = EventEnvelopeV1.from_domain(event())
    message = persistent_message(envelope)
    assert message.message_id == str(envelope.event_id)
    assert message.correlation_id == str(envelope.correlation_id)
    assert message.type == envelope.event_name
    assert message.headers["tenant_id"] == str(envelope.tenant_id)
    assert message.headers["schema_version"] == 1


def test_retry_configuration_is_bounded() -> None:
    valid = Settings(event_retry_delays_seconds="1,10,300")
    assert valid.retry_delays_seconds == (1, 10, 300)
    invalid = Settings(event_retry_delays_seconds="0,30")
    with pytest.raises(ValueError, match="EVENT_RETRY"):
        _ = invalid.retry_delays_seconds


def incoming_message(envelope: EventEnvelopeV1) -> SimpleNamespace:
    return SimpleNamespace(
        body=envelope.message_body(),
        content_type="application/json",
        message_id=str(envelope.event_id),
        type=envelope.event_name,
        correlation_id=str(envelope.correlation_id),
        timestamp=envelope.occurred_at,
        headers={"x-cyrvanta-attempt": 0},
        ack=AsyncMock(),
    )


async def test_transient_failure_is_routed_to_first_retry() -> None:
    envelope = EventEnvelopeV1.from_domain(event())
    message = incoming_message(envelope)
    retry = AsyncMock()
    deadletter = AsyncMock()
    consumer = EventConsumer(
        AsyncMock(),
        AsyncMock(),
        Settings(event_retry_delays_seconds="1,2,3"),
        {},
    )
    consumer._topology = RabbitTopology(  # noqa: SLF001
        events=AsyncMock(), retry=retry, deadletter=deadletter
    )
    await consumer._retry_or_deadletter(  # type: ignore[arg-type]  # noqa: SLF001
        message, 0, "dependency_unavailable", permanent=False
    )
    assert retry.publish.await_count == 1
    assert retry.publish.await_args.kwargs["routing_key"] == "traceability.1"
    deadletter.publish.assert_not_awaited()
    message.ack.assert_awaited_once()


async def test_permanent_failure_is_deadlettered_without_retry() -> None:
    envelope = EventEnvelopeV1.from_domain(event())
    message = incoming_message(envelope)
    retry = AsyncMock()
    deadletter = AsyncMock()
    consumer = EventConsumer(AsyncMock(), AsyncMock(), Settings(), {})
    consumer._topology = RabbitTopology(  # noqa: SLF001
        events=AsyncMock(), retry=retry, deadletter=deadletter
    )
    await consumer._retry_or_deadletter(  # type: ignore[arg-type]  # noqa: SLF001
        message, 0, "unsupported_schema", permanent=True
    )
    retry.publish.assert_not_awaited()
    assert deadletter.publish.await_count == 1
    assert deadletter.publish.await_args.kwargs["routing_key"] == envelope.event_name
    message.ack.assert_awaited_once()
