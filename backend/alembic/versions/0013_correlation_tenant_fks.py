"""Harden correlation and incident evidence tenant foreign keys."""

from alembic import op

revision = "0013_correlation_tenant_fks"
down_revision = "0012_deterministic_correlation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE correlation_runs
          DROP CONSTRAINT correlation_runs_incident_id_fkey,
          ADD CONSTRAINT fk_correlation_run_incident_tenant
            FOREIGN KEY (incident_id, tenant_id)
            REFERENCES incidents(id, tenant_id);
        """
    )
    op.execute(
        """
        ALTER TABLE incident_alerts
          DROP CONSTRAINT incident_alerts_incident_id_fkey,
          DROP CONSTRAINT incident_alerts_alert_id_fkey,
          ADD CONSTRAINT fk_incident_alert_incident_tenant
            FOREIGN KEY (incident_id, tenant_id)
            REFERENCES incidents(id, tenant_id),
          ADD CONSTRAINT fk_incident_alert_alert_tenant
            FOREIGN KEY (alert_id, tenant_id)
            REFERENCES alert_references(id, tenant_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE incident_alerts
          DROP CONSTRAINT fk_incident_alert_alert_tenant,
          DROP CONSTRAINT fk_incident_alert_incident_tenant,
          ADD CONSTRAINT incident_alerts_incident_id_fkey
            FOREIGN KEY (incident_id) REFERENCES incidents(id),
          ADD CONSTRAINT incident_alerts_alert_id_fkey
            FOREIGN KEY (alert_id) REFERENCES alert_references(id);
        """
    )
    op.execute(
        """
        ALTER TABLE correlation_runs
          DROP CONSTRAINT fk_correlation_run_incident_tenant,
          ADD CONSTRAINT correlation_runs_incident_id_fkey
            FOREIGN KEY (incident_id) REFERENCES incidents(id);
        """
    )
