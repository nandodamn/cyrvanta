import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[3]
RUNTIME_FIELDS = {
    "active",
    "createdAt",
    "id",
    "shared",
    "tags",
    "updatedAt",
    "versionId",
}


def canonical_workflow(workflow: dict[str, Any]) -> bytes:
    material = {key: value for key, value in workflow.items() if key not in RUNTIME_FIELDS}
    return json.dumps(material, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def test_released_simulation_digest_matches_migration_and_manifest() -> None:
    workflow = ROOT / "infrastructure" / "n8n" / "workflows" / "simulate-user-block.json"
    digest = hashlib.sha256(
        canonical_workflow(json.loads(workflow.read_text(encoding="utf-8"))[0])
    ).hexdigest()
    manifest = json.loads(
        (ROOT / "infrastructure" / "n8n" / "manifest.json").read_text(encoding="utf-8")
    )
    entry = next(item for item in manifest["workflows"] if item["code"] == "simulate-user-block")
    migration = (
        ROOT / "backend" / "alembic" / "versions" / "0017_finalize_simulated_user_block.py"
    ).read_text(encoding="utf-8")
    assert digest in migration
    assert entry["sha256"] == digest
    assert entry["file"] == "workflows/simulate-user-block.json"
    assert entry["version"] == "1.0.0"


def test_simulation_migration_is_additive_tenant_scoped_and_non_destructive() -> None:
    migration = (
        ROOT / "backend" / "alembic" / "versions" / "0017_finalize_simulated_user_block.py"
    ).read_text(encoding="utf-8")
    assert "provisional-demo-1" in migration
    assert "SET active = false" in migration
    assert "'MODERATE', 'SYNTHETIC', 'APPROVED'" in migration
    assert "'execution_mode', 'action', 'result'" in migration
    assert "released simulated user-block executions exist" in migration
    assert "DROP TABLE" not in migration
    assert "SET active = true" not in migration


def test_dispatch_outcomes_are_additive_tenant_scoped_and_append_only() -> None:
    migration = (
        ROOT / "backend" / "alembic" / "versions" / "0018_append_only_dispatch_outcomes.py"
    ).read_text(encoding="utf-8")
    dispatcher = (
        ROOT
        / "backend"
        / "src"
        / "cyrvanta"
        / "modules"
        / "playbooks"
        / "infrastructure"
        / "dispatcher.py"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE playbook_execution_attempt_outcomes" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "GRANT SELECT, INSERT ON playbook_execution_attempt_outcomes" in migration
    assert "REVOKE UPDATE, DELETE ON playbook_execution_attempt_outcomes" in migration
    assert "dispatch attempt outcomes exist; export them before downgrade" in migration
    assert "attempt.status =" not in dispatcher
    assert "attempt.error_code =" not in dispatcher
