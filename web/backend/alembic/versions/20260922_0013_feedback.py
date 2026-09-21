"""Add public feedback records and image attachments."""

from alembic import op
import sqlalchemy as sa


revision = "20260922_0013"
down_revision = "20260909_0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("nickname", sa.String(20), nullable=False, server_default=""),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("client_url", sa.String(2048), nullable=False, server_default=""),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("email_status", sa.String(16), nullable=False, server_default="disabled"),
        sa.Column("email_error", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feedback_created_at", "feedback", ["created_at"])
    op.create_table(
        "feedback_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("feedback_id", sa.Integer(), sa.ForeignKey("feedback.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_url", sa.String(2048), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feedback_attachments_feedback_id", "feedback_attachments", ["feedback_id"])


def downgrade():
    op.drop_index("ix_feedback_attachments_feedback_id", table_name="feedback_attachments")
    op.drop_table("feedback_attachments")
    op.drop_index("ix_feedback_created_at", table_name="feedback")
    op.drop_table("feedback")
