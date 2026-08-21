"""Record where an audited action came from.

The audit answered who did what and never from where, which is the other half
of the question an auditor asks -- and the half that separates a supervisor
approving a containment from their desk from the same credentials approving it
from an address nobody in the organisation recognises. The product documentation
had claimed this column existed for some time; it did not.

Nullable, and it stays nullable. Rows written before this migration cannot say
where they came from, and background work legitimately has no client address:
a scheduler expiring a memory is not acting from anywhere. Inventing a value
for either -- the server's own address, the last request seen -- would put a
fact in the one table that exists to be trusted.

45 characters holds an IPv6 address with an IPv4-mapped suffix, the longest
form this can take.

Revision ID: 0033_audit_source_address
Revises: 0032_memory_ai_author
"""

from alembic import op

revision = "0033_audit_source_address"
down_revision = "0032_memory_ai_author"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE audit_events ADD COLUMN source_address VARCHAR(45)")


def downgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP COLUMN IF EXISTS source_address")
