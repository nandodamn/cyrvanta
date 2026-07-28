"""Add provisional playbook catalog permissions."""

from alembic import op

revision = "0007_playbooks"
down_revision = "0006_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
          ('playbook.read', 'Read registered playbook metadata'),
          ('playbook.manage', 'Access playbook administration metadata')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (tenant_id, role_id, permission_id)
        SELECT r.tenant_id, r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE r.code = 'tenant-admin'
          AND p.code IN ('playbook.read', 'playbook.manage')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
          SELECT id FROM permissions
          WHERE code IN ('playbook.read', 'playbook.manage')
        )
        """
    )
    op.execute(
        "DELETE FROM permissions "
        "WHERE code IN ('playbook.read', 'playbook.manage')"
    )
