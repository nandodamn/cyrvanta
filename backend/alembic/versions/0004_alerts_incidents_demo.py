"""Add alert references, incidents, timeline, and correlation provenance."""

import os
import re

from alembic import op

revision = "0004_incidents"
down_revision = "0003_directory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_USER", "cyrvanta_app")
    if re.fullmatch(r"[a-z_][a-z0-9_]*", app_role) is None:
        raise ValueError("POSTGRES_APP_USER is not a safe PostgreSQL identifier")
    ddl = """
    CREATE TABLE alert_references (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      source text NOT NULL,
      external_id text NOT NULL,
      observed_at timestamptz NOT NULL,
      title text NOT NULL,
      category text NOT NULL,
      severity text NOT NULL CHECK (
        severity IN ('informational','low','medium','high','critical')
      ),
      asset_summary text,
      identity_summary text,
      indicator_summary text,
      raw_reference text,
      snapshot_sha256 text,
      provenance text NOT NULL,
      is_simulated boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, source, external_id)
    );
    CREATE TABLE incidents (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      code text NOT NULL,
      title text NOT NULL,
      description text NOT NULL,
      status text NOT NULL DEFAULT 'new' CHECK (
        status IN ('new','triaged','investigating','contained','resolved','closed','reopened')
      ),
      severity text NOT NULL CHECK (
        severity IN ('informational','low','medium','high','critical')
      ),
      priority integer NOT NULL CHECK (priority BETWEEN 1 AND 5),
      classification text NOT NULL,
      assignee_user_id uuid REFERENCES users(id),
      version integer NOT NULL DEFAULT 1,
      is_simulated boolean NOT NULL DEFAULT false,
      detected_at timestamptz NOT NULL,
      acknowledged_at timestamptz,
      resolved_at timestamptz,
      closed_at timestamptz,
      close_reason text,
      close_comment text,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, code)
    );
    CREATE TABLE incident_alerts (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      incident_id uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
      alert_id uuid NOT NULL REFERENCES alert_references(id) ON DELETE CASCADE,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, incident_id, alert_id)
    );
    CREATE TABLE incident_timeline_entries (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      incident_id uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
      actor_user_id uuid REFERENCES users(id),
      entry_type text NOT NULL,
      summary text NOT NULL,
      resource_type text,
      resource_id uuid,
      incident_version integer NOT NULL,
      effective_at timestamptz NOT NULL,
      recorded_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE correlation_runs (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      incident_id uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
      rule_code text NOT NULL,
      rule_version text NOT NULL,
      explanation text NOT NULL,
      input_fingerprint text NOT NULL,
      is_simulated boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, rule_code, rule_version, input_fingerprint)
    );
    CREATE INDEX ix_alert_references_tenant_time
      ON alert_references(tenant_id, observed_at DESC);
    CREATE INDEX ix_incidents_tenant_status
      ON incidents(tenant_id, status, updated_at DESC);
    CREATE INDEX ix_incident_timeline_tenant_incident
      ON incident_timeline_entries(tenant_id, incident_id, recorded_at);
    """
    for statement in ddl.split(";"):
        if statement.strip():
            op.execute(statement)
    tenant_tables = (
        "alert_references",
        "incidents",
        "incident_alerts",
        "incident_timeline_entries",
        "correlation_runs",
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
          ('alert.read', 'Read alert references'),
          ('incident.read', 'Read incidents'),
          ('incident.create', 'Create incidents and demo scenarios'),
          ('incident.assign', 'Assign incidents'),
          ('incident.update', 'Update incidents and timeline'),
          ('incident.close', 'Resolve, close, or reopen incidents')
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
            'alert.read','incident.read','incident.create','incident.assign',
            'incident.update','incident.close'
          )
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON " + ", ".join(tenant_tables) + f" TO {app_role}"
    )


def downgrade() -> None:
    for table in (
        "correlation_runs",
        "incident_timeline_entries",
        "incident_alerts",
        "incidents",
        "alert_references",
    ):
        op.execute(f"DROP TABLE {table}")
