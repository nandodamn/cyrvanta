"""Add tenant-safe response decisions, approvals, and authorizations."""

import os
import re

from alembic import op

revision = "0015_safe_decision"
down_revision = "0014_attack_risk"
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
        ALTER TABLE users
          ADD CONSTRAINT uq_users_id_tenant UNIQUE (id, tenant_id);

        CREATE TABLE response_policy_versions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          code varchar(120) NOT NULL,
          version varchar(40) NOT NULL,
          status varchar(16) NOT NULL CHECK (status IN ('DRAFT','ACTIVE','RETIRED')),
          kill_switch boolean NOT NULL DEFAULT false,
          definition jsonb NOT NULL CHECK (jsonb_typeof(definition) = 'object'),
          definition_sha256 varchar(64) NOT NULL CHECK (
            definition_sha256 ~ '^[0-9a-f]{64}$'
          ),
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_response_policy_version UNIQUE (tenant_id, code, version),
          CONSTRAINT uq_response_policy_id_tenant UNIQUE (id, tenant_id)
        );
        CREATE UNIQUE INDEX uq_response_policy_active
          ON response_policy_versions(tenant_id, code) WHERE status = 'ACTIVE';

        CREATE TABLE action_proposals (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          incident_id uuid NOT NULL,
          requester_user_id uuid NOT NULL,
          policy_version_id uuid NOT NULL,
          action_type varchar(120) NOT NULL CHECK (
            action_type IN (
              'simulate-user-block','notify-critical-incident',
              'create-security-ticket','incident-report-email'
            )
          ),
          impact varchar(20) NOT NULL CHECK (
            impact IN ('OBSERVATIONAL','LOW','MODERATE','HIGH','CRITICAL')
          ),
          requested_mode varchar(32) NOT NULL CHECK (
            requested_mode IN (
              'RECOMMENDATION_ONLY','HUMAN_APPROVAL','DUAL_APPROVAL','AUTOMATIC'
            )
          ),
          workflow_id varchar(120) NOT NULL,
          workflow_version varchar(80) NOT NULL,
          targets jsonb NOT NULL CHECK (
            jsonb_typeof(targets) = 'array'
            AND jsonb_array_length(targets) BETWEEN 1 AND 100
          ),
          parameters jsonb NOT NULL CHECK (
            jsonb_typeof(parameters) = 'object'
            AND pg_column_size(parameters) <= 32768
          ),
          evidence_refs jsonb NOT NULL CHECK (
            jsonb_typeof(evidence_refs) = 'array'
            AND jsonb_array_length(evidence_refs) <= 32
          ),
          incident_version integer NOT NULL CHECK (incident_version > 0),
          is_simulated boolean NOT NULL,
          fingerprint varchar(64) NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
          status varchar(24) NOT NULL CHECK (
            status IN (
              'AWAITING_APPROVAL','DENIED','AUTHORIZED','REJECTED',
              'EXPIRED','REVOKED'
            )
          ),
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_action_proposal_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT uq_action_proposal_fingerprint UNIQUE (tenant_id, fingerprint),
          CONSTRAINT fk_action_proposal_incident_tenant
            FOREIGN KEY (incident_id, tenant_id) REFERENCES incidents(id, tenant_id),
          CONSTRAINT fk_action_proposal_requester_tenant
            FOREIGN KEY (requester_user_id, tenant_id) REFERENCES users(id, tenant_id),
          CONSTRAINT fk_action_proposal_policy_tenant
            FOREIGN KEY (policy_version_id, tenant_id)
            REFERENCES response_policy_versions(id, tenant_id)
        );

        CREATE TABLE response_policy_evaluations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          proposal_id uuid NOT NULL,
          policy_version_id uuid NOT NULL,
          outcome varchar(32) NOT NULL CHECK (
            outcome IN (
              'DENIED','APPROVAL_REQUIRED','DUAL_APPROVAL_REQUIRED',
              'ELIGIBLE_FOR_AUTOMATIC'
            )
          ),
          required_approvals smallint NOT NULL CHECK (required_approvals BETWEEN 0 AND 2),
          reason_codes jsonb NOT NULL CHECK (
            jsonb_typeof(reason_codes) = 'array'
            AND jsonb_array_length(reason_codes) BETWEEN 1 AND 16
          ),
          input_fingerprint varchar(64) NOT NULL CHECK (
            input_fingerprint ~ '^[0-9a-f]{64}$'
          ),
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_policy_evaluation_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT uq_policy_evaluation_fingerprint
            UNIQUE (tenant_id, proposal_id, input_fingerprint),
          CONSTRAINT fk_policy_evaluation_proposal_tenant
            FOREIGN KEY (proposal_id, tenant_id) REFERENCES action_proposals(id, tenant_id),
          CONSTRAINT fk_policy_evaluation_policy_tenant
            FOREIGN KEY (policy_version_id, tenant_id)
            REFERENCES response_policy_versions(id, tenant_id)
        );

        CREATE TABLE approval_requests (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          proposal_id uuid NOT NULL,
          evaluation_id uuid NOT NULL,
          required_approvals smallint NOT NULL CHECK (required_approvals BETWEEN 1 AND 2),
          status varchar(24) NOT NULL CHECK (
            status IN ('PENDING','APPROVED','REJECTED','EXPIRED','REVOKED')
          ),
          expires_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_approval_request_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT uq_approval_request_proposal UNIQUE (tenant_id, proposal_id),
          CONSTRAINT fk_approval_request_proposal_tenant
            FOREIGN KEY (proposal_id, tenant_id) REFERENCES action_proposals(id, tenant_id),
          CONSTRAINT fk_approval_request_evaluation_tenant
            FOREIGN KEY (evaluation_id, tenant_id)
            REFERENCES response_policy_evaluations(id, tenant_id),
          CONSTRAINT ck_approval_request_expiry CHECK (expires_at > created_at)
        );

        CREATE TABLE approval_decisions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          approval_request_id uuid NOT NULL,
          actor_user_id uuid NOT NULL,
          decision varchar(16) NOT NULL CHECK (decision IN ('APPROVE','REJECT')),
          reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 1000),
          proposal_fingerprint varchar(64) NOT NULL CHECK (
            proposal_fingerprint ~ '^[0-9a-f]{64}$'
          ),
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_approval_decision_request_tenant
            FOREIGN KEY (approval_request_id, tenant_id)
            REFERENCES approval_requests(id, tenant_id),
          CONSTRAINT fk_approval_decision_actor_tenant
            FOREIGN KEY (actor_user_id, tenant_id) REFERENCES users(id, tenant_id),
          CONSTRAINT uq_approval_decision_actor
            UNIQUE (tenant_id, approval_request_id, actor_user_id)
        );

        CREATE TABLE action_authorizations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          proposal_id uuid NOT NULL,
          approval_request_id uuid NOT NULL,
          proposal_fingerprint varchar(64) NOT NULL CHECK (
            proposal_fingerprint ~ '^[0-9a-f]{64}$'
          ),
          status varchar(16) NOT NULL CHECK (
            status IN ('ACTIVE','CONSUMED','EXPIRED','REVOKED')
          ),
          expires_at timestamptz NOT NULL,
          consumed_at timestamptz,
          revoked_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_action_authorization_id_tenant UNIQUE (id, tenant_id),
          CONSTRAINT uq_action_authorization_request
            UNIQUE (tenant_id, approval_request_id),
          CONSTRAINT fk_action_authorization_proposal_tenant
            FOREIGN KEY (proposal_id, tenant_id) REFERENCES action_proposals(id, tenant_id),
          CONSTRAINT fk_action_authorization_request_tenant
            FOREIGN KEY (approval_request_id, tenant_id)
            REFERENCES approval_requests(id, tenant_id),
          CONSTRAINT ck_action_authorization_expiry CHECK (expires_at > created_at),
          CONSTRAINT ck_action_authorization_terminal_time CHECK (
            (status = 'ACTIVE' AND consumed_at IS NULL AND revoked_at IS NULL)
            OR (status = 'CONSUMED' AND consumed_at IS NOT NULL AND revoked_at IS NULL)
            OR (status = 'EXPIRED' AND consumed_at IS NULL)
            OR (status = 'REVOKED' AND consumed_at IS NULL AND revoked_at IS NOT NULL)
          )
        );

        CREATE INDEX ix_action_proposals_incident
          ON action_proposals(tenant_id, incident_id, created_at DESC);
        CREATE INDEX ix_approval_requests_status
          ON approval_requests(tenant_id, status, expires_at);
        CREATE INDEX ix_approval_decisions_request
          ON approval_decisions(tenant_id, approval_request_id, created_at);
        CREATE INDEX ix_action_authorizations_status
          ON action_authorizations(tenant_id, status, expires_at);
        """
    )
    op.execute(
        """
        CREATE FUNCTION enforce_approval_separation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
          requester uuid;
        BEGIN
          SELECT p.requester_user_id INTO requester
          FROM approval_requests r
          JOIN action_proposals p
            ON p.id = r.proposal_id AND p.tenant_id = r.tenant_id
          WHERE r.id = NEW.approval_request_id
            AND r.tenant_id = NEW.tenant_id;
          IF requester IS NULL OR requester = NEW.actor_user_id THEN
            RAISE EXCEPTION 'requester cannot approve the proposal';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER approval_decisions_separation
        BEFORE INSERT ON approval_decisions
        FOR EACH ROW EXECUTE FUNCTION enforce_approval_separation()
        """
    )
    tenant_tables = (
        "response_policy_versions",
        "action_proposals",
        "response_policy_evaluations",
        "approval_requests",
        "approval_decisions",
        "action_authorizations",
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
        WITH policy_material AS (
          SELECT jsonb_build_object(
            'automatic_enabled', false,
            'authorization_ttl_seconds', 300,
            'approval_ttl_seconds', 1800,
            'critical_actions', 'DENIED',
            'high_actions', 'DUAL_APPROVAL',
            'low_actions', 'HUMAN_APPROVAL',
            'moderate_actions', 'HUMAN_APPROVAL',
            'observational_actions', 'HUMAN_APPROVAL',
            'version', '1'
          ) definition
        )
        INSERT INTO response_policy_versions (
          tenant_id, code, version, status, kill_switch,
          definition, definition_sha256
        )
        SELECT t.id, 'default-response-policy', '1', 'ACTIVE', false,
               definition, encode(digest(definition::text, 'sha256'), 'hex')
        FROM tenants t CROSS JOIN policy_material
        """
    )
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
          ('response.request', 'Create tenant response proposals'),
          ('response.policy.evaluate', 'Evaluate tenant response policy'),
          ('response.approve', 'Approve or reject tenant response proposals'),
          ('response.authorize', 'Issue tenant response authorizations'),
          ('response.revoke', 'Revoke tenant response authorizations'),
          ('response.read', 'Read tenant response decisions'),
          ('response.policy.manage', 'Manage tenant response policy versions')
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
            'response.request','response.policy.evaluate','response.approve',
            'response.authorize','response.revoke','response.read',
            'response.policy.manage'
          )
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        "GRANT SELECT ON response_policy_versions TO " + app_role
    )
    op.execute(
        "GRANT SELECT, INSERT ON action_proposals, response_policy_evaluations, "
        "approval_requests, approval_decisions, action_authorizations TO " + app_role
    )
    op.execute("GRANT UPDATE (status) ON action_proposals TO " + app_role)
    op.execute("GRANT UPDATE (status) ON approval_requests TO " + app_role)
    op.execute(
        "GRANT UPDATE (status, consumed_at, revoked_at) ON action_authorizations TO "
        + app_role
    )
    op.execute(
        "REVOKE UPDATE, DELETE ON approval_decisions, "
        "response_policy_evaluations FROM " + app_role
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM action_proposals)
             OR EXISTS (SELECT 1 FROM approval_decisions)
             OR EXISTS (SELECT 1 FROM action_authorizations)
          THEN
            RAISE EXCEPTION
              'response decision history exists; export and remove it before downgrade';
          END IF;
        END
        $$;
        """
    )
    _statements(
        """
        DROP TRIGGER approval_decisions_separation ON approval_decisions;
        DROP FUNCTION enforce_approval_separation();
        DROP TABLE action_authorizations;
        DROP TABLE approval_decisions;
        DROP TABLE approval_requests;
        DROP TABLE response_policy_evaluations;
        DROP TABLE action_proposals;
        DROP TABLE response_policy_versions;
        ALTER TABLE users DROP CONSTRAINT uq_users_id_tenant;
        """
    )
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
          SELECT id FROM permissions
          WHERE code IN (
            'response.request','response.policy.evaluate','response.approve',
            'response.authorize','response.revoke','response.read',
            'response.policy.manage'
          )
        )
        """
    )
    op.execute(
        """
        DELETE FROM permissions
        WHERE code IN (
          'response.request','response.policy.evaluate','response.approve',
          'response.authorize','response.revoke','response.read',
          'response.policy.manage'
        )
        """
    )
