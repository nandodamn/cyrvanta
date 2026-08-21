"""Let a memory have no human author, and check separation against the version.

Two things this changes, both about the same question: who wrote this?

The database triggers -- the last word on separation, below anything the
service does -- read the author off the *candidate*, which is only the author
of version one. Migration 0030 gave versions their own author and fixed the
service; the triggers still pointed at the old column, so after a correction
they would have protected the wrong person: the original author blocked from
reviewing work they did not write, and the actual writer free to approve their
own. They now read the version.

And the author column was NOT NULL, which made an AI-suggested candidate
impossible to store. The specification has always allowed the AI to draft a
candidate for a person to review; it could not be built because there was
nobody to name as its author. Inventing a service user would be worse -- a
non-person in the directory, assignable to roles, appearing as an actor in
audit records, conceivably able to sign in. An AI suggestion genuinely has no
human author, so the honest representation is nobody.

That representation makes the separation rules fall out correctly on their own:
with no author to exclude, any analyst may review an AI suggestion, and the
activation trigger still refuses a null actor, so nothing can activate itself.

Revision ID: 0032_memory_ai_author
Revises: 0031_supervisor_activates_memory
"""

from alembic import op

revision = "0032_memory_ai_author"
down_revision = "0031_supervisor_activates_memory"
branch_labels = None
depends_on = None

REVIEW_SEPARATION = """
CREATE OR REPLACE FUNCTION enforce_memory_review_separation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM memory_candidate_versions v
    WHERE v.id = NEW.version_id AND v.tenant_id = NEW.tenant_id
      AND v.created_by_user_id = NEW.reviewer_user_id
  ) THEN RAISE EXCEPTION 'memory author cannot review own version'; END IF;
  RETURN NEW;
END $$
"""

ACTIVATION_SEPARATION = """
CREATE OR REPLACE FUNCTION enforce_memory_activation_separation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.to_status = 'ACTIVE' THEN
    IF NEW.actor_user_id IS NULL OR EXISTS (
      SELECT 1 FROM memory_candidate_versions v
      WHERE v.id = NEW.version_id AND v.tenant_id = NEW.tenant_id
        AND v.created_by_user_id = NEW.actor_user_id
    ) THEN RAISE EXCEPTION 'memory author cannot activate own version'; END IF;
    IF NOT EXISTS (
      SELECT 1 FROM memory_reviews r
      WHERE r.version_id = NEW.version_id AND r.tenant_id = NEW.tenant_id AND r.decision = 'APPROVE'
    ) THEN RAISE EXCEPTION 'approved review required before activation'; END IF;
  END IF;
  RETURN NEW;
END $$
"""

# The original definitions, restored on downgrade so the pair stays symmetric.
OLD_REVIEW_SEPARATION = """
CREATE OR REPLACE FUNCTION enforce_memory_review_separation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM memory_candidate_versions v
    JOIN memory_candidates c ON c.id = v.candidate_id AND c.tenant_id = v.tenant_id
    WHERE v.id = NEW.version_id AND v.tenant_id = NEW.tenant_id
      AND c.created_by_user_id = NEW.reviewer_user_id
  ) THEN RAISE EXCEPTION 'memory author cannot review own version'; END IF;
  RETURN NEW;
END $$
"""

OLD_ACTIVATION_SEPARATION = """
CREATE OR REPLACE FUNCTION enforce_memory_activation_separation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.to_status = 'ACTIVE' THEN
    IF NEW.actor_user_id IS NULL OR EXISTS (
      SELECT 1 FROM memory_candidate_versions v
      JOIN memory_candidates c ON c.id = v.candidate_id AND c.tenant_id = v.tenant_id
      WHERE v.id = NEW.version_id AND v.tenant_id = NEW.tenant_id
        AND c.created_by_user_id = NEW.actor_user_id
    ) THEN RAISE EXCEPTION 'memory author cannot activate own version'; END IF;
    IF NOT EXISTS (
      SELECT 1 FROM memory_reviews r
      WHERE r.version_id = NEW.version_id AND r.tenant_id = NEW.tenant_id AND r.decision = 'APPROVE'
    ) THEN RAISE EXCEPTION 'approved review required before activation'; END IF;
  END IF;
  RETURN NEW;
END $$
"""


def upgrade() -> None:
    op.execute("ALTER TABLE memory_candidates ALTER COLUMN created_by_user_id DROP NOT NULL")
    op.execute(
        "ALTER TABLE memory_candidate_versions ALTER COLUMN created_by_user_id DROP NOT NULL"
    )
    op.execute(REVIEW_SEPARATION)
    op.execute(ACTIVATION_SEPARATION)


def downgrade() -> None:
    op.execute(OLD_REVIEW_SEPARATION)
    op.execute(OLD_ACTIVATION_SEPARATION)
    # Restoring NOT NULL would fail while an AI-suggested candidate exists, and
    # it should: there is no human author to invent for it. Those must be
    # rejected or superseded first.
    op.execute(
        "ALTER TABLE memory_candidate_versions ALTER COLUMN created_by_user_id SET NOT NULL"
    )
    op.execute("ALTER TABLE memory_candidates ALTER COLUMN created_by_user_id SET NOT NULL")
