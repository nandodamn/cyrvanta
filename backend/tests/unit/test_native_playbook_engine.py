import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
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
