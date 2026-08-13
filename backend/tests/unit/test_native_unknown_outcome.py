from cyrvanta.modules.playbooks.application.engine_ports import ActionResult
from cyrvanta.modules.playbooks.domain.models import ExecutionStatus
from cyrvanta.modules.playbooks.infrastructure.native_engine import NativePlaybookDispatcher


def test_uncertain_external_result_propagates_as_unknown() -> None:
    result = ActionResult(
        succeeded=False,
        output={},
        error_code="PLAYBOOK_ACTION_OUTCOME_UNKNOWN",
    )

    assert NativePlaybookDispatcher._action_outcome_status(result) == "UNKNOWN"
    assert (
        NativePlaybookDispatcher._rejection_execution_status(result.error_code)
        == ExecutionStatus.UNKNOWN.value
    )


def test_definitive_action_results_keep_success_or_failure() -> None:
    succeeded = ActionResult(succeeded=True, output={})
    failed = ActionResult(succeeded=False, output={}, error_code="PLAYBOOK_ACTION_FAILED")

    assert NativePlaybookDispatcher._action_outcome_status(succeeded) == "SUCCEEDED"
    assert NativePlaybookDispatcher._action_outcome_status(failed) == "FAILED"
    assert (
        NativePlaybookDispatcher._rejection_execution_status(failed.error_code)
        == ExecutionStatus.FAILED.value
    )
