"""Give each memory version its own author.

A correction to a governed memory is a new immutable version, and the person
who writes it is not always the person who proposed the first one. The
separation rules -- the author cannot review, the author cannot activate --
were reading the author off the *candidate*, which is only the author of
version one.

So the moment a second person corrected a memory, the rules would have
protected the wrong person: the original author blocked from reviewing work
they did not write, and the actual writer free to approve their own. The
column that closes that hole did not exist, so neither did the correction
path that would have exposed it.

Backfilled from the candidate, which is exactly right for every version that
exists today: all of them are version one.

Revision ID: 0030_memory_version_author
Revises: 0029_incident_collaborators
"""

from alembic import op

revision = "0030_memory_version_author"
down_revision = "0029_incident_collaborators"
branch_labels = None
depends_on = None

TABLE = "memory_candidate_versions"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {TABLE} ADD COLUMN created_by_user_id UUID")
    # These tables force row level security, so even the owner sees nothing
    # without a tenant in scope. The backfill runs once per tenant.
    op.execute(
        f"""
        DO $$
        DECLARE tenant RECORD;
        BEGIN
          FOR tenant IN SELECT id FROM tenants LOOP
            PERFORM set_config('app.current_tenant_id', tenant.id::text, true);
            UPDATE {TABLE} v
            SET created_by_user_id = c.created_by_user_id
            FROM memory_candidates c
            WHERE c.id = v.candidate_id
              AND v.tenant_id = tenant.id
              AND v.created_by_user_id IS NULL;
          END LOOP;
          PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """
    )
    op.execute(f"ALTER TABLE {TABLE} ALTER COLUMN created_by_user_id SET NOT NULL")
    op.execute(
        f"ALTER TABLE {TABLE} ADD CONSTRAINT {TABLE}_created_by_fkey "
        f"FOREIGN KEY (created_by_user_id) REFERENCES users(id)"
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {TABLE}_created_by_fkey")
    op.execute(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS created_by_user_id")
