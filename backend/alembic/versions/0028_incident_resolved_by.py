"""Record who declared an incident technically resolved.

`resolved_at` said when it happened and nothing said by whom, so the one
question a reviewer needs answered -- whose work am I accepting? -- could not
be answered from the incident at all.

It also left a hole in the separation. The rule that an owner cannot close
their own case protects the common path, but an incident with no assignee can
be resolved by a supervisor who is then free to close it: the same person
declaring the work finished and accepting that it is. Knowing who resolved it
is what lets that be refused.

Nullable on purpose. Incidents resolved before this column existed cannot say
who did it, and inventing an answer -- the assignee, the last actor -- would be
worse than an honest blank in the one record meant to be trusted.

Revision ID: 0028_incident_resolved_by
Revises: 0027_soc_system_roles
"""

from alembic import op

revision = "0028_incident_resolved_by"
down_revision = "0027_soc_system_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE incidents ADD COLUMN resolved_by_user_id UUID")
    op.execute(
        "ALTER TABLE incidents ADD CONSTRAINT incidents_resolved_by_user_id_fkey "
        "FOREIGN KEY (resolved_by_user_id) REFERENCES users(id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE incidents DROP CONSTRAINT IF EXISTS incidents_resolved_by_user_id_fkey")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS resolved_by_user_id")
