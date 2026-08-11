import ast
from pathlib import Path

TENANT_MODELS = (
    "ActionAuthorizationModel",
    "ActionProposalModel",
    "ApprovalDecisionModel",
    "ApprovalRequestModel",
    "IncidentModel",
    "PolicyEvaluationModel",
    "ResponsePolicyVersionModel",
    "UserModel",
)


def test_every_decision_select_has_an_explicit_tenant_predicate() -> None:
    source = (
        Path(__file__).parents[2]
        / "src"
        / "cyrvanta"
        / "modules"
        / "decision"
        / "application"
        / "service.py"
    ).read_text(encoding="utf-8")
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
            f"tenant predicate missing for {model} near line {node.lineno}"
        )
        checked += 1

    assert checked >= 18
