"""Bootstrap tenant identity, RBAC, and audit with RLS."""

import os
import re

from alembic import op

revision = "0001_bootstrap"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_USER", "cyrvanta_app")
    if re.fullmatch(r"[a-z_][a-z0-9_]*", app_role) is None:
        raise ValueError("POSTGRES_APP_USER is not a safe PostgreSQL identifier")
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    bootstrap_ddl = """
    CREATE TABLE tenants (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      name text NOT NULL,
      status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended')),
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE users (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      email text NOT NULL UNIQUE,
      password_hash text NOT NULL,
      display_name text NOT NULL,
      is_active boolean NOT NULL DEFAULT true,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE roles (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      code text NOT NULL,
      name text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, code)
    );
    CREATE TABLE permissions (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      code text NOT NULL UNIQUE,
      description text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE user_roles (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, user_id, role_id)
    );
    CREATE TABLE role_permissions (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
      permission_id uuid NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, role_id, permission_id)
    );
    CREATE TABLE audit_events (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      actor_user_id uuid REFERENCES users(id),
      action text NOT NULL,
      resource_type text NOT NULL,
      resource_id uuid,
      outcome text NOT NULL,
      correlation_id uuid NOT NULL,
      details jsonb NOT NULL DEFAULT '{}'::jsonb,
      occurred_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_users_tenant ON users(tenant_id);
    CREATE INDEX ix_audit_tenant_time ON audit_events(tenant_id, occurred_at DESC);
    """
    for statement in bootstrap_ddl.split(";"):
        if statement.strip():
            op.execute(statement)
    for table in ("users", "roles", "user_roles", "role_permissions", "audit_events"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        auth_lookup = (
            " OR (current_setting('app.auth_lookup', true) = 'true')" if table == "users" else ""
        )
        tenant_setting = "nullif(current_setting('app.current_tenant_id', true), '')::uuid"
        op.execute(
            f"""CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = {tenant_setting}{auth_lookup})
            WITH CHECK (tenant_id = {tenant_setting})"""
        )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "tenants, users, roles, permissions, user_roles, role_permissions, audit_events "
        f"TO {app_role}"
    )


def downgrade() -> None:
    for table in (
        "audit_events",
        "role_permissions",
        "user_roles",
        "permissions",
        "roles",
        "users",
        "tenants",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
