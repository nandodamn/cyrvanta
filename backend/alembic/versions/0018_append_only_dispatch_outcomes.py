"""Add immutable technical outcomes for playbook dispatch attempts."""

import os

from alembic import op

revision = "0018_dispatch_outcomes"
down_revision = "0017_finalize_simulation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    app_role = os.environ.get("POSTGRES_APP_ROLE", "cyrvanta_app")
    op.execute(
        """
        CREATE TABLE playbook_execution_attempt_outcomes (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id uuid NOT NULL REFERENCES tenants(id),
          attempt_id uuid NOT NULL,
          status varchar(24) NOT NULL CHECK (
            status IN ('DISPATCHED', 'FAILED', 'UNKNOWN')
          ),
          error_code varchar(80),
          occurred_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_playbook_attempt_outcome
            UNIQUE (tenant_id, attempt_id),
          CONSTRAINT uq_playbook_attempt_outcome_id_tenant
            UNIQUE (id, tenant_id),
          CONSTRAINT fk_playbook_attempt_outcome_attempt_tenant
            FOREIGN KEY (attempt_id, tenant_id)
            REFERENCES playbook_execution_attempts(id, tenant_id)
        )
        """
    )
    op.execute("ALTER TABLE playbook_execution_attempt_outcomes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE playbook_execution_attempt_outcomes FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY playbook_execution_attempt_outcomes_tenant_isolation
          ON playbook_execution_attempt_outcomes
          USING (
            tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid
          )
          WITH CHECK (
            tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::uuid
          )
        """
    )
    op.execute("GRANT SELECT, INSERT ON playbook_execution_attempt_outcomes TO " + app_role)
    op.execute("REVOKE UPDATE, DELETE ON playbook_execution_attempt_outcomes FROM " + app_role)


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM playbook_execution_attempt_outcomes)
          THEN
            RAISE EXCEPTION
              'dispatch attempt outcomes exist; export them before downgrade';
          END IF;
        END
        $$
        """
    )
    op.execute("DROP TABLE playbook_execution_attempt_outcomes")
