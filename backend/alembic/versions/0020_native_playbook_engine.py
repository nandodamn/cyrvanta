# ruff: noqa: E501, S608
"""Add the tenant-scoped native playbook engine persistence."""

import os

from alembic import op

revision = "0020_native_playbook_engine"
down_revision = "0019_governed_memory"
branch_labels = None
depends_on = None

TABLES = (
    "playbook_step_executions",
    "playbook_step_attempts",
    "playbook_step_attempt_outcomes",
    "native_action_bindings",
)

PERMISSIONS = (
    "playbook.view",
    "playbook.author",
    "playbook.review",
    "playbook.publish",
    "playbook.execute",
    "playbook.cancel",
    "automation.credential.prepare",
    "automation.live.enable",
)


def _statements(sql: str) -> None:
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_ROLE", "cyrvanta_app")
    _statements(
        """
        ALTER TABLE playbook_definitions
          ADD COLUMN description_es varchar(2000),
          ADD COLUMN description_en varchar(2000);

        ALTER TABLE playbook_versions
          ADD COLUMN portable_artifact jsonb,
          ADD COLUMN portable_schema_version varchar(16),
          ADD COLUMN validated_sha256 varchar(64),
          ADD COLUMN validated_at timestamptz,
          ADD COLUMN validated_by_user_id uuid,
          ADD CONSTRAINT ck_playbook_version_portable_artifact CHECK (
            (portable_artifact IS NULL AND portable_schema_version IS NULL)
            OR (
              jsonb_typeof(portable_artifact) = 'object'
              AND portable_schema_version = '1.0'
              AND octet_length(portable_artifact::text) <= 262144
            )
          ),
          ADD CONSTRAINT ck_playbook_version_validation CHECK (
            (validated_sha256 IS NULL AND validated_at IS NULL
              AND validated_by_user_id IS NULL)
            OR (
              validated_sha256 ~ '^[0-9a-f]{64}$'
              AND validated_at IS NOT NULL
              AND validated_by_user_id IS NOT NULL
              AND validated_sha256 = artifact_sha256
            )
          ),
          ADD CONSTRAINT fk_playbook_version_validated_by_tenant
            FOREIGN KEY (validated_by_user_id, tenant_id)
            REFERENCES users(id, tenant_id);

        ALTER TABLE automation_engine_bindings
          DROP CONSTRAINT automation_engine_bindings_engine_type_check,
          DROP CONSTRAINT ck_automation_binding_active,
          ALTER COLUMN adapter_workflow_id DROP NOT NULL,
          ALTER COLUMN webhook_path DROP NOT NULL,
          ALTER COLUMN key_id DROP NOT NULL,
          ADD CONSTRAINT ck_automation_binding_engine_type CHECK (
            engine_type IN ('NATIVE', 'N8N')
          ),
          ADD CONSTRAINT ck_automation_binding_engine_fields CHECK (
            (engine_type = 'N8N' AND adapter_workflow_id IS NOT NULL
              AND webhook_path IS NOT NULL AND key_id IS NOT NULL)
            OR
            (engine_type = 'NATIVE' AND adapter_workflow_id IS NULL
              AND webhook_path IS NULL AND key_id IS NULL)
          ),
          ADD CONSTRAINT ck_automation_binding_active CHECK (
            NOT active OR (
              sync_status = 'SYNCHRONIZED'
              AND observed_digest = desired_digest
            )
          );

        CREATE TABLE playbook_step_executions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          execution_id uuid NOT NULL,
          step_id varchar(64) NOT NULL,
          step_type varchar(16) NOT NULL CHECK (step_type IN ('ACTION','CONDITION')),
          action_code varchar(96),
          action_version varchar(80),
          status varchar(24) NOT NULL CHECK (
            status IN (
              'PENDING','READY','CLAIMED','RUNNING','SUCCEEDED','FAILED',
              'SKIPPED','CANCELLED','UNKNOWN'
            )
          ),
          input_sha256 varchar(64) NOT NULL CHECK (
            input_sha256 ~ '^[0-9a-f]{64}$'
          ),
          result jsonb CHECK (
            result IS NULL OR (
              jsonb_typeof(result) = 'object'
              AND octet_length(result::text) <= 65536
            )
          ),
          error_code varchar(80),
          claimed_at timestamptz,
          completed_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_playbook_step_action_fields CHECK (
            (step_type = 'ACTION' AND action_code IS NOT NULL
              AND action_version IS NOT NULL)
            OR
            (step_type = 'CONDITION' AND action_code IS NULL
              AND action_version IS NULL)
          ),
          CONSTRAINT uq_playbook_step_execution UNIQUE (
            tenant_id, execution_id, step_id
          ),
          CONSTRAINT uq_playbook_step_execution_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT fk_playbook_step_execution_tenant
            FOREIGN KEY (execution_id, tenant_id)
            REFERENCES playbook_executions(id, tenant_id)
        );
        CREATE INDEX ix_playbook_step_execution_history
          ON playbook_step_executions (tenant_id, execution_id, created_at);
        CREATE INDEX ix_playbook_step_execution_pending
          ON playbook_step_executions (tenant_id, status, created_at)
          WHERE status NOT IN ('SUCCEEDED','FAILED','SKIPPED','CANCELLED');

        CREATE TABLE playbook_step_attempts (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          step_execution_id uuid NOT NULL,
          attempt_number smallint NOT NULL CHECK (attempt_number BETWEEN 1 AND 3),
          claim_id uuid NOT NULL,
          idempotency_key varchar(128) NOT NULL,
          input_sha256 varchar(64) NOT NULL CHECK (
            input_sha256 ~ '^[0-9a-f]{64}$'
          ),
          started_at timestamptz NOT NULL,
          deadline_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_playbook_step_attempt_deadline CHECK (deadline_at > started_at),
          CONSTRAINT uq_playbook_step_attempt_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT uq_playbook_step_attempt_number UNIQUE (
            tenant_id, step_execution_id, attempt_number
          ),
          CONSTRAINT uq_playbook_step_attempt_claim UNIQUE (tenant_id, claim_id),
          CONSTRAINT uq_playbook_step_attempt_idempotency UNIQUE (
            tenant_id, idempotency_key
          ),
          CONSTRAINT fk_playbook_step_attempt_tenant
            FOREIGN KEY (step_execution_id, tenant_id)
            REFERENCES playbook_step_executions(id, tenant_id)
        );

        CREATE TABLE playbook_step_attempt_outcomes (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          attempt_id uuid NOT NULL,
          outcome_event_id uuid NOT NULL,
          sequence smallint NOT NULL CHECK (sequence BETWEEN 1 AND 32767),
          status varchar(24) NOT NULL CHECK (
            status IN ('SUCCEEDED','FAILED','TIMED_OUT','UNKNOWN')
          ),
          result jsonb CHECK (
            result IS NULL OR (
              jsonb_typeof(result) = 'object'
              AND octet_length(result::text) <= 65536
            )
          ),
          result_sha256 varchar(64),
          error_code varchar(80),
          safe_detail text CHECK (safe_detail IS NULL OR length(safe_detail) <= 2000),
          occurred_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_playbook_step_outcome_digest CHECK (
            (result IS NULL AND result_sha256 IS NULL)
            OR (result IS NOT NULL AND result_sha256 ~ '^[0-9a-f]{64}$')
          ),
          CONSTRAINT uq_playbook_step_outcome_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT uq_playbook_step_outcome_event UNIQUE (
            tenant_id, outcome_event_id
          ),
          CONSTRAINT uq_playbook_step_outcome_sequence UNIQUE (
            tenant_id, attempt_id, sequence
          ),
          CONSTRAINT fk_playbook_step_outcome_attempt_tenant
            FOREIGN KEY (attempt_id, tenant_id)
            REFERENCES playbook_step_attempts(id, tenant_id)
        );

        CREATE TABLE native_action_bindings (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          action_code varchar(96) NOT NULL,
          action_version varchar(80) NOT NULL,
          connector_type varchar(32) NOT NULL CHECK (
            connector_type IN ('SIMULATED','HTTP_ALLOWLISTED')
          ),
          credential_key_id varchar(120),
          configuration jsonb NOT NULL CHECK (jsonb_typeof(configuration) = 'object'),
          configuration_sha256 varchar(64) NOT NULL CHECK (
            configuration_sha256 ~ '^[0-9a-f]{64}$'
          ),
          active boolean NOT NULL DEFAULT false,
          created_by_user_id uuid NOT NULL,
          last_verified_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_native_action_binding_credential CHECK (
            (connector_type = 'SIMULATED' AND credential_key_id IS NULL)
            OR
            (connector_type = 'HTTP_ALLOWLISTED' AND credential_key_id IS NOT NULL)
          ),
          CONSTRAINT uq_native_action_binding_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT uq_native_action_binding_action UNIQUE (
            tenant_id, action_code, action_version
          ),
          CONSTRAINT fk_native_action_binding_created_by_tenant
            FOREIGN KEY (created_by_user_id, tenant_id)
            REFERENCES users(id, tenant_id)
        );
        """
    )
    for table in TABLES:
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
          ('playbook.view', 'View tenant playbook definitions and native metadata'),
          ('playbook.author', 'Create tenant playbook definitions and draft versions'),
          ('playbook.review', 'Validate and review tenant playbook versions'),
          ('playbook.publish', 'Publish immutable tenant playbook versions'),
          ('playbook.execute', 'Dry-run approved tenant playbooks'),
          ('playbook.cancel', 'Cancel safely cancellable tenant playbook executions'),
          ('automation.credential.prepare', 'Prepare write-only automation credentials'),
          ('automation.live.enable', 'Participate in separately approved live enablement')
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
            'playbook.view','playbook.author','playbook.review','playbook.publish',
            'playbook.execute','playbook.cancel','automation.credential.prepare',
            'automation.live.enable'
          )
        ON CONFLICT DO NOTHING
        """
    )
    op.execute("GRANT INSERT ON playbook_definitions TO " + app_role)
    op.execute("GRANT INSERT ON playbook_versions TO " + app_role)
    op.execute(
        "GRANT UPDATE (validated_sha256, validated_at, validated_by_user_id, status, "
        "approved_by_user_id, approved_at) ON playbook_versions TO " + app_role
    )
    op.execute("GRANT SELECT, INSERT ON playbook_step_executions TO " + app_role)
    op.execute(
        "GRANT UPDATE (status, result, error_code, claimed_at, completed_at) "
        "ON playbook_step_executions TO " + app_role
    )
    op.execute(
        "GRANT SELECT, INSERT ON playbook_step_attempts, "
        "playbook_step_attempt_outcomes TO " + app_role
    )
    op.execute(
        "REVOKE UPDATE, DELETE ON playbook_step_attempts, "
        "playbook_step_attempt_outcomes FROM " + app_role
    )
    op.execute("GRANT SELECT, INSERT ON native_action_bindings TO " + app_role)
    op.execute(
        "GRANT UPDATE (credential_key_id, configuration, configuration_sha256, active, "
        "last_verified_at) ON native_action_bindings TO " + app_role
    )
    op.execute("REVOKE DELETE ON native_action_bindings FROM " + app_role)


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM playbook_step_executions)
             OR EXISTS (SELECT 1 FROM playbook_step_attempts)
             OR EXISTS (SELECT 1 FROM playbook_step_attempt_outcomes)
             OR EXISTS (SELECT 1 FROM native_action_bindings)
             OR EXISTS (
               SELECT 1 FROM automation_engine_bindings WHERE engine_type = 'NATIVE'
             )
             OR EXISTS (
               SELECT 1 FROM playbook_versions WHERE portable_artifact IS NOT NULL
             )
             OR EXISTS (
               SELECT 1 FROM playbook_definitions
               WHERE description_es IS NOT NULL OR description_en IS NOT NULL
             )
          THEN
            RAISE EXCEPTION
              'native playbook evidence exists; export and remove it before downgrade';
          END IF;
        END
        $$;
        """
    )
    _statements(
        """
        DROP TABLE playbook_step_attempt_outcomes;
        DROP TABLE playbook_step_attempts;
        DROP TABLE playbook_step_executions;
        DROP TABLE native_action_bindings;

        ALTER TABLE automation_engine_bindings
          DROP CONSTRAINT ck_automation_binding_active,
          DROP CONSTRAINT ck_automation_binding_engine_fields,
          DROP CONSTRAINT ck_automation_binding_engine_type,
          ALTER COLUMN adapter_workflow_id SET NOT NULL,
          ALTER COLUMN webhook_path SET NOT NULL,
          ALTER COLUMN key_id SET NOT NULL,
          ADD CONSTRAINT automation_engine_bindings_engine_type_check CHECK (
            engine_type = 'N8N'
          ),
          ADD CONSTRAINT ck_automation_binding_active CHECK (
            NOT active OR (
              sync_status = 'SYNCHRONIZED'
              AND observed_digest = desired_digest
            )
          );

        ALTER TABLE playbook_versions
          DROP CONSTRAINT fk_playbook_version_validated_by_tenant,
          DROP CONSTRAINT ck_playbook_version_validation,
          DROP CONSTRAINT ck_playbook_version_portable_artifact,
          DROP COLUMN validated_by_user_id,
          DROP COLUMN validated_at,
          DROP COLUMN validated_sha256,
          DROP COLUMN portable_schema_version,
          DROP COLUMN portable_artifact;

        ALTER TABLE playbook_definitions
          DROP COLUMN description_en,
          DROP COLUMN description_es;
        """
    )
    _statements(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
          SELECT id FROM permissions
          WHERE code IN (
            'playbook.view','playbook.author','playbook.review','playbook.publish',
            'playbook.execute','playbook.cancel','automation.credential.prepare',
            'automation.live.enable'
          )
        );
        DELETE FROM permissions
        WHERE code IN (
          'playbook.view','playbook.author','playbook.review','playbook.publish',
          'playbook.execute','playbook.cancel','automation.credential.prepare',
          'automation.live.enable'
        );
        """
    )

