"""Let an owner bring people in without handing over the case.

An incident often needs someone else -- a network engineer, a database
administrator, a second analyst -- and the only tools available were to assign
it away or to let the whole tenant act on it. Neither is right: the first moves
accountability, the second removes it.

A collaborator can add notes, attach evidence and take part in the work. They
cannot declare the incident resolved, close it, or reassign it, because none of
those are contributions to a case -- they are judgements about it, and the
person accountable for the case is still the owner.

Added and removed explicitly, and audited both ways: who was allowed near a
case and when is part of its record.

Revision ID: 0029_incident_collaborators
Revises: 0028_incident_resolved_by
"""

from alembic import op

revision = "0029_incident_collaborators"
down_revision = "0028_incident_resolved_by"
branch_labels = None
depends_on = None

TABLE = "incident_collaborators"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {TABLE} (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id),
          incident_id UUID NOT NULL REFERENCES incidents(id),
          user_id UUID NOT NULL REFERENCES users(id),
          added_by_user_id UUID NOT NULL REFERENCES users(id),
          reason VARCHAR(500),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    # One row per person per incident: adding someone twice is not a second
    # kind of participation, and two rows would make removal ambiguous.
    op.execute(
        f"CREATE UNIQUE INDEX uq_incident_collaborator "
        f"ON {TABLE}(tenant_id, incident_id, user_id)"
    )
    op.execute(f"CREATE INDEX ix_incident_collaborator_incident ON {TABLE}(tenant_id, incident_id)")

    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
        USING (
          tenant_id =
          nullif(current_setting('app.current_tenant_id', true), '')::uuid
        )
        WITH CHECK (
          tenant_id =
          nullif(current_setting('app.current_tenant_id', true), '')::uuid
        )"""
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE}")
    op.execute(f"DROP TABLE IF EXISTS {TABLE}")
