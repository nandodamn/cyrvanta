"""Add deterministic multi-source correlation."""

import os
import re

from alembic import op

revision = "0012_deterministic_correlation"
down_revision = "0011_claim_invariants"
branch_labels = None
depends_on = None


def _execute_statements(ddl: str) -> None:
    for statement in ddl.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_USER", "cyrvanta_app")
    if re.fullmatch(r"[a-z_][a-z0-9_]*", app_role) is None:
        raise ValueError("POSTGRES_APP_USER is not a safe PostgreSQL identifier")

    _execute_statements(
        """
        CREATE TABLE correlation_rule_versions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          rule_code varchar(120) NOT NULL,
          version varchar(40) NOT NULL,
          status varchar(16) NOT NULL CHECK (
            status IN ('DRAFT','ACTIVE','RETIRED')
          ),
          definition jsonb NOT NULL CHECK (
            jsonb_typeof(definition) = 'object'
          ),
          definition_sha256 varchar(64) NOT NULL CHECK (
            definition_sha256 ~ '^[0-9a-f]{64}$'
          ),
          activated_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_correlation_rule_version
            UNIQUE (rule_code, version)
        );

        CREATE UNIQUE INDEX uq_correlation_rule_active
          ON correlation_rule_versions(rule_code)
          WHERE status = 'ACTIVE';

        ALTER TABLE correlation_runs
          ALTER COLUMN incident_id DROP NOT NULL,
          ADD COLUMN rule_definition_sha256 varchar(64),
          ADD COLUMN grouping_key_hash varchar(64),
          ADD COLUMN score smallint,
          ADD COLUMN threshold smallint,
          ADD COLUMN window_start timestamptz,
          ADD COLUMN window_end timestamptz,
          ADD COLUMN claim_id uuid,
          ADD COLUMN result_type varchar(32),
          ADD COLUMN schema_version integer NOT NULL DEFAULT 1,
          ADD CONSTRAINT uq_correlation_runs_id_tenant UNIQUE (id, tenant_id);

        UPDATE correlation_runs
        SET rule_definition_sha256 =
              encode(digest('legacy-demo-v0', 'sha256'), 'hex'),
            grouping_key_hash = input_fingerprint,
            score = 0,
            threshold = 0,
            result_type = 'LEGACY_SIMULATED_V0',
            schema_version = 0;

        ALTER TABLE correlation_runs
          ALTER COLUMN rule_definition_sha256 SET NOT NULL,
          ALTER COLUMN grouping_key_hash SET NOT NULL,
          ALTER COLUMN score SET NOT NULL,
          ALTER COLUMN threshold SET NOT NULL,
          ALTER COLUMN result_type SET NOT NULL,
          ALTER COLUMN result_type SET DEFAULT 'MATCHED',
          ADD CONSTRAINT ck_correlation_run_hashes CHECK (
            rule_definition_sha256 ~ '^[0-9a-f]{64}$'
            AND grouping_key_hash ~ '^[0-9a-f]{64}$'
            AND input_fingerprint ~ '^[0-9a-f]{64}$'
          ),
          ADD CONSTRAINT ck_correlation_run_score CHECK (
            score BETWEEN 0 AND 100
            AND threshold BETWEEN 0 AND 100
          ),
          ADD CONSTRAINT ck_correlation_run_window CHECK (
            (schema_version = 0 AND window_start IS NULL AND window_end IS NULL)
            OR
            (schema_version > 0 AND window_start IS NOT NULL
              AND window_end IS NOT NULL AND window_end > window_start)
          ),
          ADD CONSTRAINT fk_correlation_run_claim_tenant
            FOREIGN KEY (claim_id, tenant_id)
            REFERENCES claims(id, tenant_id);

        CREATE INDEX ix_correlation_runs_tenant_incident
          ON correlation_runs(tenant_id, incident_id, created_at DESC);
        CREATE INDEX ix_correlation_runs_tenant_group
          ON correlation_runs(
            tenant_id, rule_code, rule_version, grouping_key_hash, created_at DESC
          );

        CREATE TABLE correlation_members (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          correlation_run_id uuid NOT NULL,
          finding_id uuid NOT NULL,
          revision_id uuid NOT NULL,
          role varchar(16) NOT NULL CHECK (
            role IN ('TRIGGER','SUPPORTING','CONTEXT')
          ),
          sort_order integer NOT NULL CHECK (
            sort_order BETWEEN 0 AND 31
          ),
          selector_code varchar(120) NOT NULL,
          effective_at timestamptz NOT NULL,
          integration_id uuid NOT NULL,
          source_system varchar(80) NOT NULL,
          is_simulated boolean NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_correlation_member_run_tenant
            FOREIGN KEY (correlation_run_id, tenant_id)
            REFERENCES correlation_runs(id, tenant_id),
          CONSTRAINT fk_correlation_member_finding_tenant
            FOREIGN KEY (finding_id, tenant_id)
            REFERENCES alert_references(id, tenant_id),
          CONSTRAINT fk_correlation_member_revision_tenant
            FOREIGN KEY (revision_id, tenant_id)
            REFERENCES finding_revisions(id, tenant_id),
          CONSTRAINT uq_correlation_member_revision UNIQUE (
            tenant_id, correlation_run_id, revision_id
          ),
          CONSTRAINT uq_correlation_member_order UNIQUE (
            tenant_id, correlation_run_id, sort_order
          )
        );

        CREATE TABLE correlation_factors (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          correlation_run_id uuid NOT NULL,
          factor_code varchar(120) NOT NULL,
          matched boolean NOT NULL,
          weight smallint NOT NULL CHECK (weight BETWEEN 0 AND 100),
          contribution smallint NOT NULL CHECK (
            contribution BETWEEN 0 AND weight
          ),
          evidence_revision_ids uuid[] NOT NULL CHECK (
            cardinality(evidence_revision_ids) BETWEEN 1 AND 32
          ),
          explanation_code varchar(160) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_correlation_factor_run_tenant
            FOREIGN KEY (correlation_run_id, tenant_id)
            REFERENCES correlation_runs(id, tenant_id),
          CONSTRAINT uq_correlation_factor_code UNIQUE (
            tenant_id, correlation_run_id, factor_code
          )
        );

        CREATE INDEX ix_correlation_members_tenant_run
          ON correlation_members(tenant_id, correlation_run_id, sort_order);
        CREATE INDEX ix_correlation_members_tenant_revision
          ON correlation_members(tenant_id, revision_id);
        CREATE INDEX ix_correlation_factors_tenant_run
          ON correlation_factors(tenant_id, correlation_run_id);
        CREATE UNIQUE INDEX uq_incident_alert_tenant_incident_alert
          ON incident_alerts(tenant_id, incident_id, alert_id);
        """
    )

    for table in ("correlation_members", "correlation_factors"):
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
        WITH material AS (
          SELECT '{
            "candidate_limit": 500,
            "member_limit": 32,
            "partial_issue_allowlist": [],
            "selectors": [
              {"code":"auth_failure","source_system":"cyrvanta-demo-v2",
               "field":"rule_reference","value":"demo-auth-failure"},
              {"code":"auth_success","source_system":"cyrvanta-demo-v2",
               "field":"rule_reference","value":"demo-auth-success"},
              {"code":"privilege_change","source_system":"cyrvanta-demo-v2",
               "field":"rule_reference","value":"demo-privilege-change"},
              {"code":"resource_access","source_system":"cyrvanta-demo-v2",
               "field":"rule_reference","value":"demo-resource-access"},
              {"code":"auth_failure","source_system":"wazuh",
               "field":"rule_reference","value":"60122"},
              {"code":"auth_success","source_system":"wazuh",
               "field":"rule_reference","value":"60106"},
              {"code":"privilege_change","source_system":"wazuh",
               "field":"rule_reference","value":"60154"},
              {"code":"resource_access","source_system":"wazuh",
               "field":"rule_reference","value":"60107"}
            ],
            "threshold": 85,
            "window_minutes": 10
          }'::jsonb AS definition
        )
        INSERT INTO correlation_rule_versions (
          rule_code, version, status, definition, definition_sha256, activated_at
        )
        SELECT
          'credential-attack', '2', 'ACTIVE', definition,
          encode(digest(definition::text, 'sha256'), 'hex'), now()
        FROM material
        """
    )
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
          ('correlation.read', 'Read deterministic correlations'),
          ('correlation.evaluate', 'Evaluate bounded deterministic correlation'),
          ('correlation.replay', 'Replay historical correlation')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (tenant_id, role_id, permission_id)
        SELECT r.tenant_id, r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE r.code = 'tenant-admin'
          AND p.code IN ('correlation.read','correlation.evaluate')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(f"GRANT SELECT ON correlation_rule_versions TO {app_role}")
    op.execute(f"REVOKE UPDATE, DELETE ON correlation_runs FROM {app_role}")
    op.execute(
        f"GRANT UPDATE (incident_id, claim_id) ON correlation_runs TO {app_role}"
    )
    op.execute(
        "GRANT SELECT, INSERT ON correlation_members, correlation_factors "
        f"TO {app_role}"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM correlation_members)
             OR EXISTS (SELECT 1 FROM correlation_factors)
             OR EXISTS (
               SELECT 1 FROM correlation_runs WHERE schema_version > 0
             )
          THEN
            RAISE EXCEPTION
              'correlation history exists; back up and remove it before downgrade';
          END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
          SELECT id FROM permissions
          WHERE code IN (
            'correlation.read','correlation.evaluate','correlation.replay'
          )
        )
        """
    )
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN (
          'correlation.read','correlation.evaluate','correlation.replay'
        )
        """
    )
    op.execute("DROP INDEX uq_incident_alert_tenant_incident_alert")
    op.execute("DROP TABLE correlation_factors")
    op.execute("DROP TABLE correlation_members")
    op.execute("DROP INDEX ix_correlation_runs_tenant_group")
    op.execute("DROP INDEX ix_correlation_runs_tenant_incident")
    op.execute(
        """
        ALTER TABLE correlation_runs
          DROP CONSTRAINT fk_correlation_run_claim_tenant,
          DROP CONSTRAINT ck_correlation_run_window,
          DROP CONSTRAINT ck_correlation_run_score,
          DROP CONSTRAINT ck_correlation_run_hashes,
          DROP CONSTRAINT uq_correlation_runs_id_tenant,
          DROP COLUMN schema_version,
          DROP COLUMN result_type,
          DROP COLUMN claim_id,
          DROP COLUMN window_end,
          DROP COLUMN window_start,
          DROP COLUMN threshold,
          DROP COLUMN score,
          DROP COLUMN grouping_key_hash,
          DROP COLUMN rule_definition_sha256,
          ALTER COLUMN incident_id SET NOT NULL
        """
    )
    op.execute("DROP TABLE correlation_rule_versions")
