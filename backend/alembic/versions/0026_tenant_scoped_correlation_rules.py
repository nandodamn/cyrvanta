"""Scope correlation rules to a tenant.

`correlation_rule_versions` had no tenant_id, so a rule was global: publishing
one changed detection for every tenant on the platform. The only roles this
system defines are tenant-scoped, which left rule administration impossible to
expose safely -- a tenant administrator granted `correlation.manage` would have
been changing what every other tenant detects. The service was reachable only
from an operator script for exactly that reason.

Isolation outranks convenience here, so the rules move under the tenant rather
than the API staying shut.

Existing rules are copied to every tenant rather than assigned to one. They are
what each tenant detects with today, and dropping them for all but one tenant
would silently disable detection somewhere. Every tenant keeps precisely the
behaviour it had this morning.

The unique constraints have to come off before the backfill: copying a rule to
a second tenant collides with (rule_code, version) until that constraint knows
about tenants.

Revision ID: 0026_tenant_scoped_rules
Revises: 0025_retire_permissions
"""

from alembic import op

revision = "0026_tenant_scoped_rules"
down_revision = "0025_retire_permissions"
branch_labels = None
depends_on = None

TABLE = "correlation_rule_versions"


def upgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS uq_correlation_rule_active")
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS uq_correlation_rule_version")

    op.execute(f"ALTER TABLE {TABLE} ADD COLUMN tenant_id UUID")

    # Copy every existing rule to every tenant beyond the first, then claim the
    # originals for the first. Ordering by created_at keeps the choice of "the
    # first" stable rather than depending on physical row order.
    op.execute(
        f"""
        DO $$
        DECLARE
          primary_tenant UUID;
          other_tenant RECORD;
        BEGIN
          SELECT id INTO primary_tenant FROM tenants ORDER BY created_at, id LIMIT 1;
          IF primary_tenant IS NULL THEN
            RETURN;
          END IF;

          FOR other_tenant IN
            SELECT id FROM tenants WHERE id <> primary_tenant ORDER BY created_at, id
          LOOP
            INSERT INTO {TABLE} (
              id, tenant_id, rule_code, version, status,
              definition, definition_sha256, activated_at, created_at
            )
            SELECT
              gen_random_uuid(), other_tenant.id, rule_code, version, status,
              definition, definition_sha256, activated_at, created_at
            FROM {TABLE}
            WHERE tenant_id IS NULL;
          END LOOP;

          UPDATE {TABLE} SET tenant_id = primary_tenant WHERE tenant_id IS NULL;
        END $$;
        """
    )

    op.execute(f"ALTER TABLE {TABLE} ALTER COLUMN tenant_id SET NOT NULL")
    op.execute(
        f"ALTER TABLE {TABLE} ADD CONSTRAINT {TABLE}_tenant_id_fkey "
        "FOREIGN KEY (tenant_id) REFERENCES tenants(id)"
    )
    op.execute(
        f"ALTER TABLE {TABLE} ADD CONSTRAINT uq_correlation_rule_version "
        "UNIQUE (tenant_id, rule_code, version)"
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_correlation_rule_active
          ON {TABLE}(tenant_id, rule_code) WHERE status = 'ACTIVE'
        """
    )

    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
        USING (
          tenant_id =
          nullif(current_setting('app.current_tenant_id', true), '')::uuid
        )
        WITH CHECK (
          tenant_id =
          nullif(current_setting('app.current_tenant_id', true), '')::uuid
        )"""
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE}")
    op.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP INDEX IF EXISTS uq_correlation_rule_active")
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS uq_correlation_rule_version")
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {TABLE}_tenant_id_fkey")

    # Collapse back to one global copy per (rule_code, version), keeping the
    # first tenant's row, so the pre-migration shape is restored rather than a
    # table that still cannot satisfy the global unique constraint.
    op.execute(
        f"""
        DELETE FROM {TABLE} a
        USING {TABLE} b
        WHERE a.rule_code = b.rule_code
          AND a.version = b.version
          AND a.ctid > b.ctid
        """
    )
    op.execute(f"ALTER TABLE {TABLE} DROP COLUMN tenant_id")
    op.execute(
        f"ALTER TABLE {TABLE} ADD CONSTRAINT uq_correlation_rule_version "
        "UNIQUE (rule_code, version)"
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_correlation_rule_active
          ON {TABLE}(rule_code) WHERE status = 'ACTIVE'
        """
    )
