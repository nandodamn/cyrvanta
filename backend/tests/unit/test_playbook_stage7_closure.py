from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from cyrvanta.modules.playbooks.infrastructure.dispatcher import (
    DISPATCH_REQUESTED_EVENT,
    N8nPlaybookDispatcher,
)
from cyrvanta.shared.domain.events import DomainEvent


def test_dispatch_ack_rejects_false_success() -> None:
    request = httpx.Request("POST", "http://n8n/webhook/cyrvanta-live")
    response = httpx.Response(
        202,
        request=request,
        json={
            "schema_version": 1,
            "execution_id": "b044c1bb-7c72-4d85-b16f-e7aa92b5cb70",
            "adapter_execution_id": "42",
            "status": "completed",
            "received_at": "2026-07-29T20:00:00Z",
        },
    )
    with pytest.raises(ValueError, match="status"):
        N8nPlaybookDispatcher.validate_ack(
            response, execution_id="b044c1bb-7c72-4d85-b16f-e7aa92b5cb70"
        )


@pytest.mark.asyncio
async def test_failed_dispatch_is_raised_for_broker_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatcher = object.__new__(N8nPlaybookDispatcher)
    dispatcher.settings = SimpleNamespace(playbook_dispatch_enabled=True)

    async def failed_dispatch(*_args: object) -> bool:
        return False

    monkeypatch.setattr(dispatcher, "dispatch", failed_dispatch)
    event = DomainEvent.create(
        event_name=DISPATCH_REQUESTED_EVENT,
        tenant_id=uuid4(),
        aggregate_type="playbook_execution",
        aggregate_id=uuid4(),
        correlation_id=uuid4(),
        producer="test",
        payload={},
    )

    with pytest.raises(RuntimeError, match="n8n dispatch failed"):
        await dispatcher.handle(event)
