"""Add optional QQ contact to feedback records."""

from alembic import op
import sqlalchemy as sa


revision = "20260922_0014"
down_revision = "20260922_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("feedback", sa.Column("contact_qq", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("feedback", "contact_qq")
