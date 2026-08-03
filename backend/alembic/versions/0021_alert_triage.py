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
    op.add_column(
        "alert_references",
        sa.Column("triage_status", sa.String(length=32), nullable=False, server_default="UNREVIEWED"),
    )
    op.add_column(
        "alert_references",
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "alert_references",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alert_references", "reviewed_at")
    op.drop_column("alert_references", "reviewed_by_user_id")
    op.drop_column("alert_references", "triage_status")
