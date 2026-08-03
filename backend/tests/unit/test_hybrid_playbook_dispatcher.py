from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cyrvanta.modules.playbooks.infrastructure.hybrid_dispatcher import (
    HybridPlaybookDispatcher,
)


@pytest.mark.parametrize("engine_type", ["NATIVE", "N8N"])
async def test_hybrid_dispatches_to_exactly_one_bound_engine(engine_type: str) -> None:
    dispatcher = object.__new__(HybridPlaybookDispatcher)
    dispatcher.settings = SimpleNamespace(n8n_enabled=True)
    dispatcher.native = SimpleNamespace(dispatch=AsyncMock(return_value=True))
    dispatcher.n8n = SimpleNamespace(dispatch=AsyncMock(return_value=True))
    tenant_id, execution_id, correlation_id = uuid4(), uuid4(), uuid4()

    result = await dispatcher._dispatch_selected(
        engine_type, tenant_id, execution_id, correlation_id, None
    )

    assert result is True
    assert dispatcher.native.dispatch.await_count == (1 if engine_type == "NATIVE" else 0)
    assert dispatcher.n8n.dispatch.await_count == (1 if engine_type == "N8N" else 0)


async def test_hybrid_fails_closed_when_n8n_is_disabled() -> None:
    dispatcher = object.__new__(HybridPlaybookDispatcher)
    dispatcher.settings = SimpleNamespace(n8n_enabled=False)
    dispatcher.native = SimpleNamespace(dispatch=AsyncMock())
    dispatcher.n8n = SimpleNamespace(dispatch=AsyncMock())

    result = await dispatcher._dispatch_selected("N8N", uuid4(), uuid4(), uuid4(), None)

    assert result is None
    dispatcher.native.dispatch.assert_not_awaited()
    dispatcher.n8n.dispatch.assert_not_awaited()
