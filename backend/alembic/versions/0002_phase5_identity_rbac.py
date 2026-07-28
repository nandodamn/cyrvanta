"""Complete the phase 5 tenant identity and RBAC bootstrap."""

from alembic import op

revision = "0002_phase5"
down_revision = "0001_bootstrap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tenants ADD COLUMN slug text")
    op.execute(
        "UPDATE tenants SET slug = 'tenant-' || left(replace(id::text, '-', ''), 12) "
        "WHERE slug IS NULL"
    )
    op.execute("ALTER TABLE tenants ALTER COLUMN slug SET NOT NULL")
    op.execute("ALTER TABLE tenants ADD CONSTRAINT uq_tenants_slug UNIQUE (slug)")
    op.execute("ALTER TABLE users DROP CONSTRAINT users_email_key")
    op.execute("ALTER TABLE users ADD CONSTRAINT uq_users_tenant_email UNIQUE (tenant_id, email)")
    op.execute("ALTER TABLE roles ADD COLUMN is_system boolean NOT NULL DEFAULT false")
    op.execute("UPDATE roles SET is_system = true WHERE code = 'tenant-admin'")

    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
          ('tenant.read', 'Read the effective tenant'),
          ('tenant.manage', 'Manage the effective tenant'),
          ('user.read', 'Read users in the effective tenant'),
          ('user.manage', 'Manage users in the effective tenant'),
          ('role.read', 'Read roles and assignable permissions'),
          ('role.manage', 'Manage roles in the effective tenant'),
          ('audit.read', 'Read audit events in the effective tenant')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (tenant_id, role_id, permission_id)
        SELECT r.tenant_id, r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE r.code = 'tenant-admin'
          AND p.code IN (
            'tenant.read', 'tenant.manage', 'user.read', 'user.manage',
            'role.read', 'role.manage', 'audit.read'
          )
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE roles DROP COLUMN is_system")
    op.execute("ALTER TABLE users DROP CONSTRAINT uq_users_tenant_email")
    op.execute("ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email)")
    op.execute("ALTER TABLE tenants DROP CONSTRAINT uq_tenants_slug")
    op.execute("ALTER TABLE tenants DROP COLUMN slug")
