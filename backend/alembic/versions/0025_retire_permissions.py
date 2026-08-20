"""Retire permissions that grant nothing.

Eleven permissions were seeded by the specifications for phases 18 through 21A
and never enforced anywhere: no router requires them, no service checks them,
they appear nowhere in the source. They were not accidents -- each is a
deliberate capability from an approved phase -- but none of those phases
shipped the code that would read them.

Nine of them are already granted to `tenant-admin`. That is the reason to
remove them rather than leave them listed. A grant made today gives an
administrator a capability that does nothing, which is misleading on its own,
but the real problem is what happens later: the moment the corresponding
feature ships, a permission granted long ago and never reviewed becomes live
without anyone deciding it should be. Authorization would be inherited from a
decision nobody remembers making.

They are also visible in the administration screen, where an operator can grant
them believing they enable something.

When each phase is implemented, its own migration seeds the permission it needs
and the grant is made deliberately, against a capability that exists. The
downgrade restores exactly what was here, so this is reversible.

Revision ID: 0025_retire_permissions
Revises: 0024_wazuh_action_binding
"""

from alembic import op

revision = "0025_retire_permissions"
down_revision = "0024_wazuh_action_binding"
branch_labels = None
depends_on = None

# code -> description, exactly as the original migrations seeded them, so the
# downgrade restores the catalogue rather than an approximation of it.
RETIRED_PERMISSIONS: dict[str, str] = {
    "analysis.read": "Read persisted incident analysis",
    "automation.credential.prepare": "Prepare write-only automation credentials",
    "automation.live.enable": "Participate in separately approved live enablement",
    "automation.reconcile": "Reconcile automation engine state",
    "correlation.replay": "Replay historical correlation",
    "mitre.mapping.validate": "Validate tenant ATT&CK evidence mappings",
    "playbook.release": "Approve immutable tenant playbook versions",
    "response.authorize": "Issue tenant response authorizations",
    "response.policy.evaluate": "Evaluate tenant response policy",
    "response.policy.manage": "Manage tenant response policy versions",
    "threat-knowledge.manage": "Manage global threat knowledge releases",
}

# Nine of the eleven were granted to tenant-admin. `correlation.replay` and
# `threat-knowledge.manage` never were -- 0012 granted only read and evaluate,
# and a global release capability was deliberately not tenant-scoped. The
# downgrade restores that distinction rather than granting all eleven, so a
# rollback returns the catalogue as it was and not a broader version of it.
_GRANTED_ROLE = "tenant-admin"
_WAS_GRANTED: tuple[str, ...] = (
    "analysis.read",
    "automation.credential.prepare",
    "automation.live.enable",
    "automation.reconcile",
    "mitre.mapping.validate",
    "playbook.release",
    "response.authorize",
    "response.policy.evaluate",
    "response.policy.manage",
)


def _codes_sql() -> str:
    return ", ".join(f"'{code}'" for code in sorted(RETIRED_PERMISSIONS))


def upgrade() -> None:
    codes = _codes_sql()
    # Both statements run inside a per-tenant context. Alembic connects as the
    # application role, which is subject to forced row-level security, so a
    # plain DELETE against role_permissions matches nothing and a plain
    # INSERT ... SELECT FROM roles reads nothing -- silently, with no error.
    # Without this the grants disappeared only because the permission delete
    # cascades, and the downgrade restored none of them.
    op.execute(
        f"""
        DO $$
        DECLARE tenant RECORD;
        BEGIN
          FOR tenant IN SELECT id FROM tenants LOOP
            PERFORM set_config('app.current_tenant_id', tenant.id::text, true);
            DELETE FROM role_permissions
            WHERE tenant_id = tenant.id
              AND permission_id IN (SELECT id FROM permissions WHERE code IN ({codes}));
          END LOOP;
          PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """
    )
    op.execute(f"DELETE FROM permissions WHERE code IN ({codes})")


def downgrade() -> None:
    values = ", ".join(
        f"('{code}', '{description}')" for code, description in sorted(RETIRED_PERMISSIONS.items())
    )
    op.execute(
        f"""
        INSERT INTO permissions (code, description) VALUES {values}
        ON CONFLICT (code) DO NOTHING
        """
    )
    granted = ", ".join(f"'{code}'" for code in _WAS_GRANTED)
    op.execute(
        f"""
        DO $$
        DECLARE tenant RECORD;
        BEGIN
          FOR tenant IN SELECT id FROM tenants LOOP
            PERFORM set_config('app.current_tenant_id', tenant.id::text, true);
            INSERT INTO role_permissions (tenant_id, role_id, permission_id)
            SELECT r.tenant_id, r.id, p.id
            FROM roles r CROSS JOIN permissions p
            WHERE r.tenant_id = tenant.id
              AND r.code = '{_GRANTED_ROLE}'
              AND p.code IN ({granted})
            ON CONFLICT DO NOTHING;
          END LOOP;
          PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """
    )
