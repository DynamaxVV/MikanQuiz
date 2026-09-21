"""Add server-side reusable explanations keyed by font option."""

from alembic import op
import sqlalchemy as sa


revision = "20260922_0015"
down_revision = "20260922_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "font_explanation_caches",
        sa.Column("font_option_id", sa.Integer(), sa.ForeignKey("font_options.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("explanation", sa.String(length=1000), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("font_explanation_caches")
