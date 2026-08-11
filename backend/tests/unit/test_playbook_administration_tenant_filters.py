import ast
from pathlib import Path

TENANT_MODELS = (
    "PlaybookDefinitionModel",
    "PlaybookVersionModel",
    "AutomationEngineBindingModel",
    "PlaybookExecutionModel",
    "NativeActionBindingModel",
)


def _source() -> str:
    return (
        Path(__file__).parents[2]
        / "src"
        / "cyrvanta"
        / "modules"
        / "playbooks"
        / "application"
        / "administration_service.py"
    ).read_text(encoding="utf-8")


def test_every_administration_select_for_tenant_models_has_tenant_predicate() -> None:
    tree = ast.parse(_source())
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    checked = 0
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "select"
            and node.args
        ):
            continue
        selected = ast.unparse(node.args[0])
        model = next((name for name in TENANT_MODELS if name in selected), None)
        if model is None:
            continue
        outer: ast.AST = node
        while isinstance(parents.get(outer), (ast.Attribute, ast.Call)):
            outer = parents[outer]
        query = ast.unparse(outer)
        assert f"{model}.tenant_id" in query, (
            f"tenant predicate missing for {model} near line {node.lineno}"
        )
        checked += 1

    assert checked >= 20


def test_tenant_context_reaches_administration_query_helpers() -> None:
    source = _source()

    assert "_locked_version(session, tenant_id, version_id)" in source
    assert "session, tenant_id, self._artifact(version)" in source
    assert "PlaybookVersionModel.tenant_id == item.tenant_id" in source
    assert "AutomationEngineBindingModel.tenant_id == item.tenant_id" in source
    assert "PlaybookExecutionModel.tenant_id == item.tenant_id" in source
