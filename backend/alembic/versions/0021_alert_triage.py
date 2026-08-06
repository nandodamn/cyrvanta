# ruff: noqa: E501, S608
"""Add alert triage status, reviewer tracking, and audit traceability."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021_alert_triage"
down_revision = "0020_native_playbook_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE alert_references ADD COLUMN IF NOT EXISTS triage_status VARCHAR(32) DEFAULT 'UNREVIEWED' NOT NULL")
    op.execute("ALTER TABLE alert_references ADD COLUMN IF NOT EXISTS reviewed_by_user_id UUID REFERENCES users(id)")
    op.execute("ALTER TABLE alert_references ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITH TIME ZONE")


def downgrade() -> None:
    op.drop_column("alert_references", "reviewed_at")
    op.drop_column("alert_references", "reviewed_by_user_id")
    op.drop_column("alert_references", "triage_status")
