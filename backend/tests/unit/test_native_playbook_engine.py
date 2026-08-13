import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cyrvanta.modules.playbooks.application.portable import (
    ConditionStep,
    PortablePlaybookV1,
)
from cyrvanta.modules.playbooks.infrastructure.native_engine import (
    NativeEngineRejected,
    NativePlaybookDispatcher,
)

FIXTURE = (
    Path(__file__).parents[3]
    / "infrastructure"
    / "playbook_engine"
    / "fixtures"
    / "simulated-notification.json"
)


def artifact() -> PortablePlaybookV1:
    return PortablePlaybookV1.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_native_runner_has_deterministic_topological_order() -> None:
    assert [step.id for step in NativePlaybookDispatcher._topological_steps(artifact())] == [
        "notify",
        "delivered",
    ]


def test_native_runner_selects_edges_from_recorded_outcomes() -> None:
    playbook = artifact()

    assert NativePlaybookDispatcher._is_selected(playbook, "notify", {}) is True
    assert (
        NativePlaybookDispatcher._is_selected(playbook, "delivered", {"notify": "SUCCESS"}) is True
    )
    assert (
        NativePlaybookDispatcher._is_selected(playbook, "delivered", {"notify": "FAILURE"}) is False
    )


def test_native_runner_evaluates_only_declarative_paths() -> None:
    condition = artifact().steps[1]
    assert isinstance(condition, ConditionStep)

    assert (
        NativePlaybookDispatcher._evaluate(
            condition.expression,
            artifact_input={},
            outputs={"notify": {"status": "DELIVERED"}},
        )
        is True
    )
    assert (
        NativePlaybookDispatcher._evaluate(
            condition.expression,
            artifact_input={},
            outputs={"notify": {"status": "FAILED"}},
        )
        is False
    )


@pytest.mark.parametrize(
    ("settings", "mode", "deadline", "expected"),
    [
        ({"automation_kill_switch": True}, "SYNTHETIC", 30, "PLAYBOOK_ENGINE_DISABLED"),
        ({"playbook_native_engine_enabled": False}, "SYNTHETIC", 30, "PLAYBOOK_ENGINE_DISABLED"),
        ({"native_enabled_tenant_ids": {"other"}}, "SYNTHETIC", 30, "PLAYBOOK_ENGINE_DISABLED"),
        ({}, "LIVE", 30, "PLAYBOOK_LIVE_DISABLED"),
        ({}, "SYNTHETIC", -1, "PLAYBOOK_DEADLINE_EXCEEDED"),
    ],
)
def test_native_runner_kill_switches_fail_closed(
    settings: dict[str, object], mode: str, deadline: int, expected: str
) -> None:
    tenant_id = uuid4()
    dispatcher = object.__new__(NativePlaybookDispatcher)
    defaults = {
        "automation_kill_switch": False,
        "playbook_native_engine_enabled": True,
        "native_enabled_tenant_ids": set(),
    }
    dispatcher.settings = SimpleNamespace(**(defaults | settings))
    execution = SimpleNamespace(
        execution_mode=mode,
        deadline_at=datetime.now(UTC) + timedelta(seconds=deadline),
    )

    with pytest.raises(NativeEngineRejected, match=expected):
        dispatcher._guard_global(tenant_id, execution)


def test_recovery_reconstructs_persisted_progress() -> None:
    rows = [
        SimpleNamespace(
            step_id="notify",
            step_type="ACTION",
            status="SUCCEEDED",
            result={"status": "DELIVERED"},
        ),
        SimpleNamespace(
            step_id="delivered",
            step_type="CONDITION",
            status="SUCCEEDED",
            result={"matched": True},
        ),
        SimpleNamespace(
            step_id="pending",
            step_type="ACTION",
            status="CLAIMED",
            result=None,
        ),
    ]

    outcomes, outputs = NativePlaybookDispatcher._progress_from_rows(rows)

    assert outcomes == {"notify": "SUCCESS", "delivered": "TRUE"}
    assert outputs["notify"] == {"status": "DELIVERED"}
    assert "pending" not in outcomes


def test_recovery_rejects_ambiguous_terminal_step() -> None:
    row = SimpleNamespace(
        step_id="notify",
        step_type="ACTION",
        status="UNKNOWN",
        result=None,
    )

    with pytest.raises(NativeEngineRejected, match="PLAYBOOK_STATE_CONFLICT"):
        NativePlaybookDispatcher._progress_from_rows([row])


def test_recovery_reuses_only_attempt_without_outcome_and_same_input() -> None:
    attempt = SimpleNamespace(input_sha256="a" * 64)

    NativePlaybookDispatcher._validate_recoverable_attempt(
        attempt, outcome_exists=None, input_digest="a" * 64
    )
    with pytest.raises(NativeEngineRejected, match="PLAYBOOK_STATE_CONFLICT"):
        NativePlaybookDispatcher._validate_recoverable_attempt(
            attempt, outcome_exists=uuid4(), input_digest="a" * 64
        )
    with pytest.raises(NativeEngineRejected, match="PLAYBOOK_STATE_CONFLICT"):
        NativePlaybookDispatcher._validate_recoverable_attempt(
            attempt, outcome_exists=None, input_digest="b" * 64
        )


def test_native_execution_lock_key_is_stable_and_tenant_scoped() -> None:
    tenant_id, execution_id = uuid4(), uuid4()

    first = NativePlaybookDispatcher._execution_lock_key(tenant_id, execution_id)

    assert first == NativePlaybookDispatcher._execution_lock_key(tenant_id, execution_id)
    assert first != NativePlaybookDispatcher._execution_lock_key(uuid4(), execution_id)
    assert -(2**63) <= first < 2**63


async def test_native_redelivery_without_execution_lease_is_a_no_op() -> None:
    dispatcher = object.__new__(NativePlaybookDispatcher)
    dispatcher._dispatch_exclusively = AsyncMock(return_value=True)

    @asynccontextmanager
    async def lease_unavailable(*_args: object):
        yield False

    dispatcher._execution_lease = lease_unavailable

    result = await dispatcher.dispatch(uuid4(), uuid4(), uuid4())

    assert result is None
    dispatcher._dispatch_exclusively.assert_not_awaited()


async def test_two_simultaneous_native_deliveries_execute_only_once() -> None:
    dispatcher = object.__new__(NativePlaybookDispatcher)
    entered = asyncio.Event()
    release = asyncio.Event()
    lease_active = False

    async def execute_once(*_args: object) -> bool:
        entered.set()
        await release.wait()
        return True

    @asynccontextmanager
    async def exclusive_lease(*_args: object):
        nonlocal lease_active
        if lease_active:
            yield False
            return
        lease_active = True
        try:
            yield True
        finally:
            lease_active = False

    dispatcher._dispatch_exclusively = AsyncMock(side_effect=execute_once)
    dispatcher._execution_lease = exclusive_lease
    tenant_id, execution_id = uuid4(), uuid4()

    first = asyncio.create_task(dispatcher.dispatch(tenant_id, execution_id, uuid4()))
    await entered.wait()
    second = asyncio.create_task(dispatcher.dispatch(tenant_id, execution_id, uuid4()))
    assert await second is None
    release.set()

    assert await first is True
    assert dispatcher._dispatch_exclusively.await_count == 1
