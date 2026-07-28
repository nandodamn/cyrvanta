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
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "0005_operations_permissions.py"
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
