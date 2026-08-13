import inspect
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
    dispatcher.settings = SimpleNamespace(
        automation_kill_switch=False,
        n8n_enabled=True,
        playbook_dispatch_enabled=True,
        playbook_live_enabled=True,
    )
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
    dispatcher.settings = SimpleNamespace(
        automation_kill_switch=False,
        n8n_enabled=False,
        playbook_dispatch_enabled=True,
        playbook_live_enabled=True,
    )
    dispatcher.native = SimpleNamespace(dispatch=AsyncMock())
    dispatcher.n8n = SimpleNamespace(dispatch=AsyncMock())

    result = await dispatcher._dispatch_selected("N8N", uuid4(), uuid4(), uuid4(), None)

    assert result is None
    dispatcher.native.dispatch.assert_not_awaited()
    dispatcher.n8n.dispatch.assert_not_awaited()


async def test_hybrid_n8n_requires_live_dispatch_switch() -> None:
    dispatcher = object.__new__(HybridPlaybookDispatcher)
    dispatcher.settings = SimpleNamespace(
        automation_kill_switch=False,
        n8n_enabled=True,
        playbook_dispatch_enabled=False,
        playbook_live_enabled=True,
    )
    dispatcher.native = SimpleNamespace(dispatch=AsyncMock())
    dispatcher.n8n = SimpleNamespace(dispatch=AsyncMock())

    result = await dispatcher._dispatch_selected("N8N", uuid4(), uuid4(), uuid4(), None)

    assert result is None
    dispatcher.n8n.dispatch.assert_not_awaited()


def test_pending_dispatch_filters_disabled_engines_and_native_tenants() -> None:
    dispatcher = object.__new__(HybridPlaybookDispatcher)
    allowed_tenant = uuid4()
    dispatcher.settings = SimpleNamespace(
        automation_kill_switch=False,
        n8n_enabled=False,
        native_enabled_tenant_ids={str(allowed_tenant)},
        playbook_dispatch_enabled=True,
        playbook_live_enabled=True,
        playbook_native_engine_enabled=True,
    )

    assert dispatcher._enabled_engines(allowed_tenant) == ("NATIVE",)
    assert dispatcher._enabled_engines(uuid4()) == ()


def test_pending_dispatch_fails_closed_when_live_is_off() -> None:
    dispatcher = object.__new__(HybridPlaybookDispatcher)
    dispatcher.settings = SimpleNamespace(
        automation_kill_switch=False,
        n8n_enabled=True,
        native_enabled_tenant_ids=set(),
        playbook_dispatch_enabled=True,
        playbook_live_enabled=False,
        playbook_native_engine_enabled=True,
    )

    assert dispatcher._enabled_engines(uuid4()) == ()


def test_pending_dispatch_round_robins_tenants() -> None:
    first_tenant, second_tenant = uuid4(), uuid4()
    first_ids = [uuid4(), uuid4(), uuid4()]
    second_ids = [uuid4(), uuid4()]

    assert list(
        HybridPlaybookDispatcher._round_robin(
            [(first_tenant, first_ids), (second_tenant, second_ids)]
        )
    ) == [
        (first_tenant, first_ids[0]),
        (second_tenant, second_ids[0]),
        (first_tenant, first_ids[1]),
        (second_tenant, second_ids[1]),
        (first_tenant, first_ids[2]),
    ]


def test_pending_dispatch_has_no_fixed_tenant_cap_and_requires_active_tenant() -> None:
    source = inspect.getsource(HybridPlaybookDispatcher.dispatch_pending)
    tenant_discovery = source.split("pending_batches", maxsplit=1)[0]

    assert ".limit(" not in tenant_discovery
    assert 'TenantModel.status == "active"' in source
