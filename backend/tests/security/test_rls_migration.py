from pathlib import Path


def test_rls_is_forced_on_every_tenant_table() -> None:
    migration = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0001_bootstrap_identity_rls.py"
    ).read_text(encoding="utf-8")
    for table in ("users", "roles", "user_roles", "role_permissions", "audit_events"):
        assert table in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_tenant_id" in migration


def test_repositories_establish_tenant_context() -> None:
    database = (
        Path(__file__).parents[2] / "src" / "cyrvanta" / "shared" / "database.py"
    ).read_text(encoding="utf-8")
    service = (
        Path(__file__).parents[2]
        / "src"
        / "cyrvanta"
        / "modules"
        / "identity"
        / "application"
        / "service.py"
    ).read_text(encoding="utf-8")
    assert "set_config('app.current_tenant_id'" in database
    assert "tenant_session(tenant_id)" in service


def test_phase5_migration_preserves_tenant_scoped_identity() -> None:
    migration = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0002_phase5_identity_rbac.py"
    ).read_text(encoding="utf-8")
    assert "uq_users_tenant_email" in migration
    assert "tenant-admin" in migration
    assert "audit.read" in migration
    assert "0001_bootstrap" in migration


def test_permission_dependency_is_deny_by_default() -> None:
    dependency = (
        Path(__file__).parents[2] / "src" / "cyrvanta" / "shared" / "dependencies.py"
    ).read_text(encoding="utf-8")
    assert "Permission denied" in dependency
    assert "HTTP_403_FORBIDDEN" in dependency
    assert "tenant_session(context.tenant_id)" in dependency


def test_operations_use_explicit_permissions() -> None:
    migration = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0005_operations_permissions.py"
    ).read_text(encoding="utf-8")
    router = (
        Path(__file__).parents[2]
        / "src"
        / "cyrvanta"
        / "modules"
        / "operations"
        / "presentation"
        / "router.py"
    ).read_text(encoding="utf-8")
    assert "analysis.request" in migration
    assert "response.execute" in migration
    assert 'require_permission("analysis.request")' in router
    assert 'require_permission("response.execute")' in router


def test_event_delivery_migration_forces_rls_and_restricts_dispatch() -> None:
    migration = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0008_event_delivery_traceability.py"
    ).read_text(encoding="utf-8")
    assert "event_outbox" in migration
    assert "event_inbox" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_tenant_id" in migration
    assert "SECURITY DEFINER" in migration
    assert "FOR UPDATE SKIP LOCKED" in migration
    assert "REVOKE ALL ON FUNCTION" in migration
    assert "tables are not empty" in migration


def test_finding_revision_migration_is_tenant_scoped_and_non_destructive() -> None:
    migration = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0009_canonical_finding_provenance.py"
    ).read_text(encoding="utf-8")
    assert "finding_revisions" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_tenant_id" in migration
    assert "uq_finding_revision_payload" in migration
    assert "payload_sha256" in migration
    assert "canonical finding data exists" in migration
    assert "GRANT SELECT, INSERT ON finding_revisions" in migration


def test_claim_ledger_is_append_only_tenant_scoped_and_fail_closed() -> None:
    migration = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0010_claim_ledger.py"
    ).read_text(encoding="utf-8")
    for table in (
        "claims",
        "claim_evidence_links",
        "claim_relationships",
        "claim_assessments",
        "claim_presentations",
    ):
        assert table in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_tenant_id" in migration
    assert "GRANT SELECT, INSERT ON" in migration
    assert "GRANT UPDATE" not in migration
    assert "GRANT DELETE" not in migration
    assert "claim type is reserved" not in migration
    assert "claim_type NOT IN ('DECISION','ACTION','RESULT')" in migration
    assert "claim ledger contains data" in migration


def test_claim_type_specific_invariants_are_database_enforced() -> None:
    migration = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0011_claim_invariants.py"
    ).read_text(encoding="utf-8")
    assert "ck_claim_hypothesis_missing" in migration
    assert "cardinality(missing_evidence) > 0" in migration
    assert "ck_claim_nondeterministic_explanation" in migration


def test_correlation_migration_is_tenant_scoped_bounded_and_non_destructive() -> None:
    migration = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0012_deterministic_correlation.py"
    ).read_text(encoding="utf-8")
    for table in (
        "correlation_runs",
        "correlation_members",
        "correlation_factors",
    ):
        assert table in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_tenant_id" in migration
    assert "fk_correlation_member_revision_tenant" in migration
    assert "uq_correlation_member_revision" in migration
    assert "candidate_limit" in migration
    assert "member_limit" in migration
    assert "correlation history exists" in migration
    assert "REVOKE UPDATE, DELETE ON correlation_runs" in migration
    assert "GRANT UPDATE (incident_id, claim_id)" in migration
    assert "correlation.replay" in migration
    assert "'correlation.read','correlation.evaluate'" in migration


def test_correlation_incident_links_use_composite_tenant_foreign_keys() -> None:
    migration = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0013_correlation_tenant_fks.py"
    ).read_text(encoding="utf-8")
    assert "fk_correlation_run_incident_tenant" in migration
    assert "fk_incident_alert_incident_tenant" in migration
    assert "fk_incident_alert_alert_tenant" in migration
    assert "FOREIGN KEY (incident_id, tenant_id)" in migration
    assert "FOREIGN KEY (alert_id, tenant_id)" in migration


def test_attack_risk_migration_is_tenant_scoped_bounded_and_append_only() -> None:
    migration = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0014_attack_risk_explainability.py"
    ).read_text(encoding="utf-8")
    for table in (
        "attack_releases",
        "attack_objects",
        "incident_attack_mappings",
        "attack_mapping_evidence",
        "risk_assessments",
        "risk_assessment_factors",
        "incident_explanations",
    ):
        assert table in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_tenant_id" in migration
    assert "num_nonnulls" in migration
    assert "FOREIGN KEY (incident_id, tenant_id)" in migration
    assert "FOREIGN KEY (finding_revision_id, tenant_id)" in migration
    assert "cardinality(selector_codes) BETWEEN 1 AND 32" in migration
    assert "GRANT SELECT, INSERT ON incident_attack_mappings" in migration
    assert "ATT&CK or risk data exists" in migration


def test_safe_decision_migration_enforces_rls_separation_and_append_only_history() -> None:
    migration = (
        Path(__file__).parents[2] / "alembic" / "versions" / "0015_safe_decision_approval.py"
    ).read_text(encoding="utf-8")
    for table in (
        "response_policy_versions",
        "action_proposals",
        "response_policy_evaluations",
        "approval_requests",
        "approval_decisions",
        "action_authorizations",
    ):
        assert table in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_tenant_id" in migration
    assert "fk_action_proposal_incident_tenant" in migration
    assert "fk_approval_decision_actor_tenant" in migration
    assert "requester cannot approve the proposal" in migration
    assert "UNIQUE (tenant_id, approval_request_id, actor_user_id)" in migration
    assert "REVOKE UPDATE, DELETE ON approval_decisions" in migration
    assert "response decision history exists" in migration
