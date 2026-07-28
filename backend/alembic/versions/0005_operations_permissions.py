"""Add explicit permissions for AI analysis and response execution."""

from alembic import op

revision = "0005_operations"
down_revision = "0004_incidents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
          ('analysis.request', 'Request bounded incident analysis'),
          ('response.execute', 'Execute an approved response workflow')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (tenant_id, role_id, permission_id)
        SELECT r.tenant_id, r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE r.code = 'tenant-admin'
          AND p.code IN ('analysis.request', 'response.execute')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
          SELECT id FROM permissions
          WHERE code IN ('analysis.request', 'response.execute')
        )
        """
    )
    op.execute(
        "DELETE FROM permissions WHERE code IN ('analysis.request', 'response.execute')"
    )
