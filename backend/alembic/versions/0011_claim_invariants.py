"""Harden type-specific claim invariants."""

from alembic import op

revision = "0011_claim_invariants"
down_revision = "0010_claim_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE claims
          ADD CONSTRAINT ck_claim_hypothesis_missing CHECK (
            claim_type <> 'HYPOTHESIS'
            OR cardinality(missing_evidence) > 0
          ),
          ADD CONSTRAINT ck_claim_nondeterministic_explanation CHECK (
            claim_type NOT IN ('INFERENCE','HYPOTHESIS','RECOMMENDATION')
            OR length(trim(explanation)) > 0
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE claims
          DROP CONSTRAINT ck_claim_nondeterministic_explanation,
          DROP CONSTRAINT ck_claim_hypothesis_missing
        """
    )
