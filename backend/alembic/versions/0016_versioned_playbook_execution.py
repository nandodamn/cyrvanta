"""Add versioned playbooks and tenant-safe automation execution."""

import os
import re

from alembic import op

revision = "0016_playbook_execution"
down_revision = "0015_safe_decision"
branch_labels = None
depends_on = None


def _statements(ddl: str) -> None:
    for statement in ddl.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_USER", "cyrvanta_app")
    if re.fullmatch(r"[a-z_][a-z0-9_]*", app_role) is None:
        raise ValueError("POSTGRES_APP_USER is not a safe PostgreSQL identifier")
    _statements(
        """
        CREATE TABLE playbook_definitions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          code varchar(120) NOT NULL,
          name_es varchar(200) NOT NULL,
          name_en varchar(200) NOT NULL,
          action_type varchar(120) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_playbook_definition UNIQUE (tenant_id, code),
          CONSTRAINT uq_playbook_definition_action UNIQUE (tenant_id, action_type),
          CONSTRAINT uq_playbook_definition_id_tenant UNIQUE (id, tenant_id)
        );

        CREATE TABLE playbook_versions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          definition_id uuid NOT NULL,
          version varchar(80) NOT NULL,
          impact varchar(20) NOT NULL CHECK (
            impact IN ('OBSERVATIONAL','LOW','MODERATE','HIGH','CRITICAL')
          ),
          classification varchar(16) NOT NULL CHECK (
            classification IN ('SYNTHETIC','LIVE')
          ),
          status varchar(16) NOT NULL CHECK (
            status IN ('DRAFT','APPROVED','RETIRED')
          ),
          workflow_code varchar(120) NOT NULL,
          artifact_sha256 varchar(64) NOT NULL CHECK (
            artifact_sha256 ~ '^[0-9a-f]{64}$'
          ),
          input_schema jsonb NOT NULL CHECK (jsonb_typeof(input_schema) = 'object'),
          result_schema jsonb NOT NULL CHECK (jsonb_typeof(result_schema) = 'object'),
          timeout_seconds integer NOT NULL CHECK (timeout_seconds BETWEEN 1 AND 3600),
          registered_by_user_id uuid,
          approved_by_user_id uuid,
          approved_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_playbook_version UNIQUE (tenant_id, definition_id, version),
          CONSTRAINT uq_playbook_version_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT fk_playbook_version_definition_tenant
            FOREIGN KEY (definition_id, tenant_id)
            REFERENCES playbook_definitions(id, tenant_id),
          CONSTRAINT fk_playbook_version_registered_by_tenant
            FOREIGN KEY (registered_by_user_id, tenant_id) REFERENCES users(id, tenant_id),
          CONSTRAINT fk_playbook_version_approved_by_tenant
            FOREIGN KEY (approved_by_user_id, tenant_id) REFERENCES users(id, tenant_id),
          CONSTRAINT ck_playbook_version_approval CHECK (
            (status = 'APPROVED' AND approved_at IS NOT NULL)
            OR (status <> 'APPROVED' AND approved_at IS NULL)
          )
        );

        CREATE TABLE automation_engine_bindings (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          playbook_version_id uuid NOT NULL,
          engine_type varchar(32) NOT NULL CHECK (engine_type = 'N8N'),
          instance_code varchar(120) NOT NULL,
          adapter_workflow_id varchar(160) NOT NULL,
          webhook_path varchar(200) NOT NULL,
          key_id varchar(120) NOT NULL,
          desired_digest varchar(64) NOT NULL CHECK (desired_digest ~ '^[0-9a-f]{64}$'),
          observed_digest varchar(64) CHECK (
            observed_digest IS NULL OR observed_digest ~ '^[0-9a-f]{64}$'
          ),
          sync_status varchar(24) NOT NULL CHECK (
            sync_status IN ('PENDING','SYNCHRONIZED','DRIFTED','ERROR')
          ),
          active boolean NOT NULL DEFAULT false,
          last_verified_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_automation_binding UNIQUE (
            tenant_id, playbook_version_id, instance_code
          ),
          CONSTRAINT uq_automation_binding_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT fk_automation_binding_version_tenant
            FOREIGN KEY (playbook_version_id, tenant_id)
            REFERENCES playbook_versions(id, tenant_id),
          CONSTRAINT ck_automation_binding_active CHECK (
            NOT active OR (
              sync_status = 'SYNCHRONIZED'
              AND observed_digest = desired_digest
            )
          )
        );

        CREATE TABLE playbook_executions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          authorization_id uuid,
          source_event_id uuid,
          proposal_id uuid,
          incident_id uuid NOT NULL,
          playbook_version_id uuid NOT NULL,
          binding_id uuid NOT NULL,
          origin varchar(32) NOT NULL CHECK (
            origin IN ('AUTHORIZED_RESPONSE','SYSTEM_NOTIFICATION')
          ),
          idempotency_key varchar(128) NOT NULL,
          proposal_fingerprint varchar(64) CHECK (
            proposal_fingerprint IS NULL OR proposal_fingerprint ~ '^[0-9a-f]{64}$'
          ),
          execution_mode varchar(16) NOT NULL CHECK (
            execution_mode IN ('SYNTHETIC','LIVE')
          ),
          status varchar(24) NOT NULL CHECK (
            status IN (
              'QUEUED','DISPATCHING','DISPATCHED','RUNNING','SUCCEEDED',
              'FAILED','TIMED_OUT','CANCELLED','UNKNOWN'
            )
          ),
          inputs jsonb NOT NULL CHECK (jsonb_typeof(inputs) = 'object'),
          result jsonb CHECK (result IS NULL OR jsonb_typeof(result) = 'object'),
          error_code varchar(80),
          adapter_execution_id varchar(200),
          claimed_at timestamptz,
          deadline_at timestamptz NOT NULL,
          completed_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_playbook_execution_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT uq_playbook_execution_idempotency
            UNIQUE (tenant_id, idempotency_key),
          CONSTRAINT uq_playbook_execution_authorization
            UNIQUE (tenant_id, authorization_id),
          CONSTRAINT uq_playbook_execution_source_event
            UNIQUE (tenant_id, source_event_id),
          CONSTRAINT fk_playbook_execution_authorization_tenant
            FOREIGN KEY (authorization_id, tenant_id)
            REFERENCES action_authorizations(id, tenant_id),
          CONSTRAINT fk_playbook_execution_proposal_tenant
            FOREIGN KEY (proposal_id, tenant_id) REFERENCES action_proposals(id, tenant_id),
          CONSTRAINT fk_playbook_execution_incident_tenant
            FOREIGN KEY (incident_id, tenant_id) REFERENCES incidents(id, tenant_id),
          CONSTRAINT fk_playbook_execution_version_tenant
            FOREIGN KEY (playbook_version_id, tenant_id)
            REFERENCES playbook_versions(id, tenant_id),
          CONSTRAINT fk_playbook_execution_binding_tenant
            FOREIGN KEY (binding_id, tenant_id)
            REFERENCES automation_engine_bindings(id, tenant_id),
          CONSTRAINT ck_playbook_execution_origin CHECK (
            (
              origin = 'AUTHORIZED_RESPONSE'
              AND authorization_id IS NOT NULL
              AND proposal_id IS NOT NULL
              AND source_event_id IS NULL
              AND proposal_fingerprint IS NOT NULL
            )
            OR (
              origin = 'SYSTEM_NOTIFICATION'
              AND authorization_id IS NULL
              AND proposal_id IS NULL
              AND source_event_id IS NOT NULL
              AND proposal_fingerprint IS NULL
            )
          ),
          CONSTRAINT ck_playbook_execution_deadline CHECK (deadline_at > created_at),
          CONSTRAINT ck_playbook_execution_terminal CHECK (
            (
              status IN ('SUCCEEDED','FAILED','TIMED_OUT','CANCELLED')
              AND completed_at IS NOT NULL
            )
            OR (
              status NOT IN ('SUCCEEDED','FAILED','TIMED_OUT','CANCELLED')
              AND completed_at IS NULL
            )
          )
        );

        CREATE TABLE playbook_execution_attempts (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          execution_id uuid NOT NULL,
          attempt_number smallint NOT NULL CHECK (attempt_number BETWEEN 1 AND 10),
          dispatch_id uuid NOT NULL,
          status varchar(24) NOT NULL CHECK (
            status IN ('DISPATCHING','DISPATCHED','FAILED','UNKNOWN')
          ),
          error_code varchar(80),
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_playbook_attempt_number
            UNIQUE (tenant_id, execution_id, attempt_number),
          CONSTRAINT uq_playbook_attempt_dispatch UNIQUE (tenant_id, dispatch_id),
          CONSTRAINT uq_playbook_attempt_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT fk_playbook_attempt_execution_tenant
            FOREIGN KEY (execution_id, tenant_id)
            REFERENCES playbook_executions(id, tenant_id)
        );

        CREATE TABLE playbook_execution_updates (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          execution_id uuid NOT NULL,
          adapter_event_id uuid NOT NULL,
          sequence smallint NOT NULL CHECK (sequence BETWEEN 1 AND 32767),
          status varchar(24) NOT NULL CHECK (
            status IN (
              'RUNNING','SUCCEEDED','FAILED','TIMED_OUT','CANCELLED','UNKNOWN'
            )
          ),
          result jsonb CHECK (result IS NULL OR jsonb_typeof(result) = 'object'),
          error_code varchar(80),
          safe_detail text CHECK (safe_detail IS NULL OR length(safe_detail) <= 2000),
          occurred_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_playbook_update_event UNIQUE (tenant_id, adapter_event_id),
          CONSTRAINT uq_playbook_update_sequence UNIQUE (tenant_id, execution_id, sequence),
          CONSTRAINT fk_playbook_update_execution_tenant
            FOREIGN KEY (execution_id, tenant_id)
            REFERENCES playbook_executions(id, tenant_id)
        );

        CREATE TABLE automation_replay_nonces (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          binding_id uuid NOT NULL,
          direction varchar(16) NOT NULL CHECK (
            direction IN ('DISPATCH','CALLBACK')
          ),
          key_id varchar(120) NOT NULL,
          nonce uuid NOT NULL,
          body_sha256 varchar(64) NOT NULL CHECK (body_sha256 ~ '^[0-9a-f]{64}$'),
          expires_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_automation_replay_nonce UNIQUE (
            tenant_id, direction, key_id, nonce
          ),
          CONSTRAINT fk_automation_nonce_binding_tenant
            FOREIGN KEY (binding_id, tenant_id)
            REFERENCES automation_engine_bindings(id, tenant_id)
        );

        CREATE INDEX ix_playbook_executions_incident
          ON playbook_executions(tenant_id, incident_id, created_at DESC);
        CREATE INDEX ix_playbook_executions_status
          ON playbook_executions(tenant_id, status, deadline_at);
        CREATE INDEX ix_automation_nonces_expiry
          ON automation_replay_nonces(tenant_id, expires_at);
        """
    )
    op.execute(
        """
        CREATE FUNCTION resolve_playbook_execution_tenant(p_execution_id uuid)
        RETURNS uuid
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT tenant_id
          FROM public.playbook_executions
          WHERE id = p_execution_id
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION resolve_playbook_execution_tenant(uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION resolve_playbook_execution_tenant(uuid) TO " + app_role
    )
    tenant_tables = (
        "playbook_definitions",
        "playbook_versions",
        "automation_engine_bindings",
        "playbook_executions",
        "playbook_execution_attempts",
        "playbook_execution_updates",
        "automation_replay_nonces",
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
          ('playbook.release', 'Approve immutable tenant playbook versions'),
          ('playbook.execution.read', 'Read tenant playbook executions'),
          ('response.execute', 'Consume an authorization and execute a playbook'),
          ('response.cancel', 'Cancel a tenant playbook execution'),
          ('automation.binding.manage', 'Manage tenant automation bindings'),
          ('automation.reconcile', 'Reconcile automation engine state')
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
            'playbook.release','playbook.execution.read','response.execute',
            'response.cancel','automation.binding.manage','automation.reconcile'
          )
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO playbook_definitions (
          tenant_id, code, name_es, name_en, action_type
        )
        SELECT t.id, seed.code, seed.name_es, seed.name_en, seed.action_type
        FROM tenants t CROSS JOIN (
          VALUES
            ('notify-critical-incident','Notificar incidente crítico',
             'Notify critical incident','notify-critical-incident'),
            ('create-security-ticket','Crear ticket de seguridad',
             'Create security ticket','create-security-ticket'),
            ('request-dual-approval','Solicitar aprobación dual',
             'Request dual approval','request-dual-approval'),
            ('simulate-user-block','Simular bloqueo de usuario',
             'Simulate user block','simulate-user-block'),
            ('incident-report-email','Enviar informe de incidente',
             'Send incident report','incident-report-email')
        ) AS seed(code, name_es, name_en, action_type)
        """
    )
    op.execute(
        """
        INSERT INTO playbook_versions (
          tenant_id, definition_id, version, impact, classification, status,
          workflow_code, artifact_sha256, input_schema, result_schema,
          timeout_seconds, approved_at
        )
        SELECT d.tenant_id, d.id,
               CASE WHEN d.code = 'simulate-user-block'
                    THEN 'provisional-demo-1' ELSE '1.0.0' END,
               CASE WHEN d.code IN ('notify-critical-incident','incident-report-email')
                    THEN 'OBSERVATIONAL' ELSE 'LOW' END,
               'SYNTHETIC', 'APPROVED',
               CASE WHEN d.code = 'simulate-user-block'
                    THEN 'cyrvanta-demo-response' ELSE d.code END,
               CASE d.code
                 WHEN 'notify-critical-incident'
                   THEN 'e532c6aaca4bd7ce048cb9a4422ec799c06360e4e6a502de7040955da3e61e0d'
                 WHEN 'create-security-ticket'
                   THEN 'a19596e37ebfaf593a886cdcfe3ae9dbfc78f10fe9616d8ebee893b6e2034776'
                 WHEN 'request-dual-approval'
                   THEN '7373f61b52b1e0c991297ad260ea6207d7519e1e62bc23d2aaa8a746a25d5f2d'
                 WHEN 'simulate-user-block'
                   THEN '90d5df07a0636e37687b8ebe86e64840f7bec124c34f061d8d303da8fe7f90d7'
                 ELSE '0ad6243fe943b8e9c40b5e8633bbf83c24cc82fc7876ae182de05608e8062ad3'
               END,
               jsonb_build_object(
                 'type', 'object',
                 'additionalProperties', false,
                 'required', jsonb_build_array('targets','parameters','evidence_refs')
               ),
               jsonb_build_object(
                 'type', 'object',
                 'additionalProperties', false,
                 'required', jsonb_build_array('simulated','effect','workflow_code')
               ),
               120, now()
        FROM playbook_definitions d
        """
    )
    op.execute(
        """
        INSERT INTO automation_engine_bindings (
          tenant_id, playbook_version_id, engine_type, instance_code,
          adapter_workflow_id, webhook_path, key_id, desired_digest,
          observed_digest, sync_status, active, last_verified_at
        )
        SELECT v.tenant_id, v.id, 'N8N', 'local-demo', v.workflow_code,
               v.workflow_code, 'local-demo-v1', v.artifact_sha256,
               CASE WHEN v.workflow_code = 'cyrvanta-demo-response'
                    THEN v.artifact_sha256 ELSE NULL END,
               CASE WHEN v.workflow_code = 'cyrvanta-demo-response'
                    THEN 'SYNCHRONIZED' ELSE 'PENDING' END,
               v.workflow_code = 'cyrvanta-demo-response',
               CASE WHEN v.workflow_code = 'cyrvanta-demo-response'
                    THEN now() ELSE NULL END
        FROM playbook_versions v
        """
    )
    op.execute(
        "GRANT SELECT ON playbook_definitions, playbook_versions TO " + app_role
    )
    op.execute(
        "GRANT SELECT, INSERT ON automation_engine_bindings, "
        "playbook_executions TO " + app_role
    )
    op.execute(
        "GRANT UPDATE (adapter_workflow_id, webhook_path, key_id, desired_digest, "
        "observed_digest, sync_status, active, last_verified_at) "
        "ON automation_engine_bindings TO " + app_role
    )
    op.execute(
        "GRANT UPDATE (status, result, error_code, adapter_execution_id, claimed_at, "
        "completed_at) ON playbook_executions TO " + app_role
    )
    op.execute(
        "GRANT SELECT, INSERT ON playbook_execution_attempts, "
        "playbook_execution_updates, automation_replay_nonces TO " + app_role
    )
    op.execute(
        "REVOKE UPDATE, DELETE ON playbook_execution_attempts, "
        "playbook_execution_updates, automation_replay_nonces FROM " + app_role
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM playbook_executions)
             OR EXISTS (SELECT 1 FROM playbook_execution_attempts)
             OR EXISTS (SELECT 1 FROM playbook_execution_updates)
          THEN
            RAISE EXCEPTION
              'playbook execution history exists; export and remove it before downgrade';
          END IF;
        END
        $$;
        """
    )
    _statements(
        """
        DROP FUNCTION resolve_playbook_execution_tenant(uuid);
        DROP TABLE automation_replay_nonces;
        DROP TABLE playbook_execution_updates;
        DROP TABLE playbook_execution_attempts;
        DROP TABLE playbook_executions;
        DROP TABLE automation_engine_bindings;
        DROP TABLE playbook_versions;
        DROP TABLE playbook_definitions;
        """
    )
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
          SELECT id FROM permissions
          WHERE code IN (
            'playbook.release','playbook.execution.read','response.execute',
            'response.cancel','automation.binding.manage','automation.reconcile'
          )
        )
        """
    )
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN (
          'playbook.release','playbook.execution.read','response.execute',
          'response.cancel','automation.binding.manage','automation.reconcile'
        )
        """
    )
