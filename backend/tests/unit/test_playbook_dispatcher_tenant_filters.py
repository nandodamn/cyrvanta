import ast
from pathlib import Path

INFRASTRUCTURE = (
    Path(__file__).parents[2] / "src" / "cyrvanta" / "modules" / "playbooks" / "infrastructure"
)
TENANT_MODELS = (
    "AutomationEngineBindingModel",
    "NativeActionBindingModel",
    "PlaybookExecutionAttemptModel",
    "PlaybookExecutionAttemptOutcomeModel",
    "PlaybookExecutionModel",
    "PlaybookStepAttemptModel",
    "PlaybookStepAttemptOutcomeModel",
    "PlaybookStepExecutionModel",
    "PlaybookVersionModel",
)


def _assert_tenant_scoped_selects(filename: str, minimum: int) -> None:
    source = (INFRASTRUCTURE / filename).read_text(encoding="utf-8")
    tree = ast.parse(source)
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
            f"tenant predicate missing for {model} in {filename}:{node.lineno}"
        )
        checked += 1

    assert checked >= minimum


def test_n8n_dispatcher_queries_are_explicitly_tenant_scoped() -> None:
    _assert_tenant_scoped_selects("dispatcher.py", minimum=10)


def test_hybrid_dispatcher_queries_are_explicitly_tenant_scoped() -> None:
    _assert_tenant_scoped_selects("hybrid_dispatcher.py", minimum=2)


def test_native_dispatcher_queries_are_explicitly_tenant_scoped() -> None:
    _assert_tenant_scoped_selects("native_engine.py", minimum=14)


def test_hybrid_join_uses_tenant_as_part_of_its_identity() -> None:
    """A binding is joined on tenant as well as id, so one tenant's execution
    can never be matched against another tenant's engine binding.

    Whitespace is collapsed before matching. Pinned to exact indentation, this
    broke the moment the formatter reflowed the expression, while the join it
    guards had not changed at all -- and a guard that fails for the wrong
    reason teaches people to edit the guard.
    """
    source = (INFRASTRUCTURE / "hybrid_dispatcher.py").read_text(encoding="utf-8")
    collapsed = " ".join(source.split())

    assert "PlaybookExecutionModel.tenant_id == AutomationEngineBindingModel.tenant_id" in collapsed
