"""Add generic, tenant-isolated security integration persistence."""

import os
import re

from alembic import op

revision = "0006_integrations"
down_revision = "0005_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_USER", "cyrvanta_app")
    if re.fullmatch(r"[a-z_][a-z0-9_]*", app_role) is None:
        raise ValueError("POSTGRES_APP_USER is not a safe PostgreSQL identifier")
    ddl = """
    CREATE TABLE integrations (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      connector_type varchar(80) NOT NULL,
      name varchar(200) NOT NULL,
      status varchar(40) NOT NULL DEFAULT 'disabled',
      configuration_schema_version varchar(40) NOT NULL,
      configuration_encrypted bytea NOT NULL,
      capabilities_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
      last_health_check_at timestamptz,
      last_successful_sync_at timestamptz,
      last_error_code varchar(80),
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, name)
    );
    CREATE TABLE integration_sync_state (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      integration_id uuid NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
      stream_type varchar(80) NOT NULL,
      cursor text,
      watermark timestamptz,
      last_processed_at timestamptz,
      last_source_timestamp timestamptz,
      status varchar(40) NOT NULL DEFAULT 'idle',
      error_count integer NOT NULL DEFAULT 0 CHECK (error_count >= 0),
      UNIQUE (tenant_id, integration_id, stream_type)
    );
    CREATE TABLE integration_health_history (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      integration_id uuid NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
      status varchar(40) NOT NULL,
      latency_ms integer CHECK (latency_ms IS NULL OR latency_ms >= 0),
      error_code varchar(80),
      error_message_redacted text,
      checked_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_integrations_tenant_type ON integrations(tenant_id, connector_type);
    CREATE INDEX ix_integration_health_tenant_time
      ON integration_health_history(tenant_id, checked_at DESC);
    """
    for statement in ddl.split(";"):
        if statement.strip():
            op.execute(statement)
    tenant_tables = (
        "integrations",
        "integration_sync_state",
        "integration_health_history",
    )
    for table in tenant_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table}_tenant_isolation ON {table}
            USING (
              tenant_id =
              nullif(current_setting('app.current_tenant_id', true), '')::uuid
            )
            WITH CHECK (
              tenant_id =
              nullif(current_setting('app.current_tenant_id', true), '')::uuid
            )"""
        )
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
          ('integration.read', 'Read connector configuration and health'),
          ('integration.manage', 'Configure and synchronize connectors')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (tenant_id, role_id, permission_id)
        SELECT r.tenant_id, r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE r.code = 'tenant-admin'
          AND p.code IN ('integration.read', 'integration.manage')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        + ", ".join(tenant_tables)
        + f" TO {app_role}"
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
          SELECT id FROM permissions
          WHERE code IN ('integration.read', 'integration.manage')
        )
        """
    )
    op.execute(
        "DELETE FROM permissions WHERE code IN ('integration.read', 'integration.manage')"
    )
    for table in (
        "integration_health_history",
        "integration_sync_state",
        "integrations",
    ):
        op.execute(f"DROP TABLE {table}")

