"""Let a SOC supervisor activate an approved memory.

`memory.activate` sat only with the tenant administrator, so publishing an
operational lesson required someone whose job is not running the SOC. In
practice that means it never happens: the analyst who wrote the lesson and the
supervisor who agreed with it both stop at approved, and the memory stays
invisible to the people it was written for.

The separation the ADR asked for is not weakened by this. That the author may
not activate their own version is enforced in code, on the version's author,
and stays exactly where it was -- unlike a permission, which is configuration a
tenant administrator can edit. What changes here is only who is allowed to be
the *other* person, and a supervisor is the role that already accepts an
analyst's work on incidents.

The tenant administrator keeps the permission. Someone has to be able to do
this in a tenant with no supervisor yet.

Revision ID: 0031_supervisor_activates_memory
Revises: 0030_memory_version_author
"""

from alembic import op

revision = "0031_supervisor_activates_memory"
down_revision = "0030_memory_version_author"
branch_labels = None
depends_on = None

ROLE = "soc-supervisor"
PERMISSIONS = ("memory.activate", "memory.disable", "memory.metrics.read")


def _grant(codes: tuple[str, ...]) -> str:
    listed = ", ".join(f"'{code}'" for code in codes)
    # These tables force row level security, so the loop puts one tenant in
    # scope at a time; without it the statement sees nothing and reports success.
    return f"""
        DO $$
        DECLARE tenant RECORD;
        BEGIN
          FOR tenant IN SELECT id FROM tenants LOOP
            PERFORM set_config('app.current_tenant_id', tenant.id::text, true);
            INSERT INTO role_permissions (tenant_id, role_id, permission_id)
            SELECT r.tenant_id, r.id, p.id
            FROM roles r CROSS JOIN permissions p
            WHERE r.tenant_id = tenant.id
              AND r.code = '{ROLE}'
              AND p.code IN ({listed})
            ON CONFLICT DO NOTHING;
          END LOOP;
          PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """


def _revoke(codes: tuple[str, ...]) -> str:
    listed = ", ".join(f"'{code}'" for code in codes)
    return f"""
        DO $$
        DECLARE tenant RECORD;
        BEGIN
          FOR tenant IN SELECT id FROM tenants LOOP
            PERFORM set_config('app.current_tenant_id', tenant.id::text, true);
            DELETE FROM role_permissions rp
            USING roles r, permissions p
            WHERE rp.role_id = r.id
              AND rp.permission_id = p.id
              AND rp.tenant_id = tenant.id
              AND r.code = '{ROLE}'
              AND p.code IN ({listed});
          END LOOP;
          PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """


def upgrade() -> None:
    op.execute(_grant(PERMISSIONS))


def downgrade() -> None:
    op.execute(_revoke(PERMISSIONS))
