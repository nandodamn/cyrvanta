from pathlib import Path


def test_native_action_binding_queries_include_explicit_tenant_filters() -> None:
    source = (
        Path(__file__).parents[2]
        / "src"
        / "cyrvanta"
        / "modules"
        / "playbooks"
        / "infrastructure"
        / "native_engine.py"
    ).read_text(encoding="utf-8")

    validation_query = source.split("async def _validate_action_bindings", maxsplit=1)[1].split(
        "async def _execute_action", maxsplit=1
    )[0]
    execution_query = source.split("async def _execute_action", maxsplit=1)[1].split(
        "async def _complete_condition", maxsplit=1
    )[0]

    assert "NativeActionBindingModel.tenant_id == tenant_id" in validation_query
    assert "NativeActionBindingModel.tenant_id == context.tenant_id" in execution_query
