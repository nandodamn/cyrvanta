"""Add tenant-scoped LDAP and Active Directory configuration."""

import os
import re

from alembic import op

revision = "0003_directory"
down_revision = "0002_phase5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_USER", "cyrvanta_app")
    if re.fullmatch(r"[a-z_][a-z0-9_]*", app_role) is None:
        raise ValueError("POSTGRES_APP_USER is not a safe PostgreSQL identifier")
    bootstrap_ddl = """
        CREATE TABLE directory_configurations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL UNIQUE REFERENCES tenants(id),
          provider_type text NOT NULL CHECK (provider_type IN ('ldap','active_directory')),
          status text NOT NULL DEFAULT 'draft'
            CHECK (status IN ('draft','active','disabled','degraded')),
          server_uri text NOT NULL,
          use_starttls boolean NOT NULL DEFAULT false,
          base_dn text NOT NULL,
          bind_dn text NOT NULL,
          bind_secret_ciphertext text NOT NULL,
          user_filter text NOT NULL,
          login_attribute text NOT NULL,
          subject_attribute text NOT NULL,
          email_attribute text NOT NULL,
          display_name_attribute text NOT NULL,
          group_base_dn text,
          group_filter text,
          group_attribute text,
          ca_certificate_pem text,
          jit_enabled boolean NOT NULL DEFAULT false,
          timeout_seconds integer NOT NULL DEFAULT 5
            CHECK (timeout_seconds BETWEEN 1 AND 30),
          last_tested_at timestamptz,
          last_test_success boolean,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE TABLE directory_identities (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          provider_type text NOT NULL,
          external_subject text NOT NULL,
          normalized_username text NOT NULL,
          last_authenticated_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (tenant_id, provider_type, external_subject),
          UNIQUE (tenant_id, user_id, provider_type)
        );
        CREATE TABLE directory_group_mappings (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          external_group text NOT NULL,
          role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (tenant_id, external_group, role_id)
        );
        ALTER TABLE user_roles ADD COLUMN assignment_source text NOT NULL DEFAULT 'manual'
          CHECK (assignment_source IN ('manual','directory'));
        CREATE INDEX ix_directory_identities_user
          ON directory_identities(tenant_id, user_id);
        """
    for statement in bootstrap_ddl.split(";"):
        if statement.strip():
            op.execute(statement)
    for table in (
        "directory_configurations",
        "directory_identities",
        "directory_group_mappings",
    ):
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
          ('directory.read', 'Read redacted directory configuration'),
          ('directory.manage', 'Manage directory configuration and mappings')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (tenant_id, role_id, permission_id)
        SELECT r.tenant_id, r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE r.code = 'tenant-admin'
          AND p.code IN ('directory.read', 'directory.manage')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "directory_configurations, directory_identities, directory_group_mappings "
        f"TO {app_role}"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE user_roles DROP COLUMN assignment_source")
    op.execute("DROP TABLE directory_group_mappings")
    op.execute("DROP TABLE directory_identities")
    op.execute("DROP TABLE directory_configurations")
