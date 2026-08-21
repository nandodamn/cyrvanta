import json
from pathlib import Path

ROOT = Path(__file__).parents[3]


def test_the_simulated_user_block_is_no_longer_offered() -> None:
    """Migration 0017 released a SYNTHETIC playbook with no steps at all.

    Proposing it produced the whole four-eyes ceremony around an action that
    did nothing, which teaches an analyst that dispatching a response is
    theatre. Blocking an account for real is compromised-account 1.0.2, whose
    step is account.disable.

    The migration stays -- it is history, and executions recorded under it are
    immutable. What must not survive is the catalogue offering the playbook or
    the manifest claiming to manage its artifact.
    """
    retired = (
        ROOT
        / "backend"
        / "src"
        / "cyrvanta"
        / "modules"
        / "playbooks"
        / "application"
        / "administration_service.py"
    ).read_text(encoding="utf-8")
    assert '"simulate-user-block",' in retired.split("RETIRED_PLAYBOOK_CODES")[1]

    manifest = json.loads(
        (ROOT / "infrastructure" / "n8n" / "manifest.json").read_text(encoding="utf-8")
    )
    assert all(item["code"] != "simulate-user-block" for item in manifest["workflows"])
    assert not (ROOT / "infrastructure" / "n8n" / "workflows" / "simulate-user-block.json").exists()


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
