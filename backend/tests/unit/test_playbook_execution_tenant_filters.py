from pathlib import Path


def _execution_service_source() -> str:
    return (
        Path(__file__).parents[2]
        / "src"
        / "cyrvanta"
        / "modules"
        / "playbooks"
        / "application"
        / "service.py"
    ).read_text(encoding="utf-8")


def test_execution_service_queries_include_explicit_tenant_filters() -> None:
    source = _execution_service_source()
    required_filters = {
        "PlaybookExecutionModel": "PlaybookExecutionModel.tenant_id == tenant_id",
        "ActionAuthorizationModel": "ActionAuthorizationModel.tenant_id == tenant_id",
        "ActionProposalModel": "ActionProposalModel.tenant_id == tenant_id",
        "PlaybookDefinitionModel": "PlaybookDefinitionModel.tenant_id == tenant_id",
        "PlaybookVersionModel": "PlaybookVersionModel.tenant_id == tenant_id",
        "AutomationEngineBindingModel": ("AutomationEngineBindingModel.tenant_id == tenant_id"),
        "PlaybookStepExecutionModel": ("PlaybookStepExecutionModel.tenant_id == tenant_id"),
        "PlaybookExecutionAttemptModel": ("PlaybookExecutionAttemptModel.tenant_id == tenant_id"),
        "PlaybookExecutionUpdateModel": ("PlaybookExecutionUpdateModel.tenant_id == tenant_id"),
        "AutomationReplayNonceModel": ("AutomationReplayNonceModel.tenant_id == tenant_id"),
    }

    for model, tenant_filter in required_filters.items():
        assert tenant_filter in source, f"missing explicit tenant filter for {model}"


def test_execution_relationship_queries_receive_tenant_context() -> None:
    source = _execution_service_source()

    assert "_locked_execution(session, tenant_id, execution_id)" in source
    assert "session, tenant_id, execution.binding_id, key_id" in source
    assert 'session, tenant_id, "DISPATCH", key_id, nonce' in source
    assert 'session, tenant_id, "CALLBACK", key_id, nonce' in source
