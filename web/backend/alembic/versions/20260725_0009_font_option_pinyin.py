"""Add pinyin column to font_options for pinyin-based sorting."""

from alembic import op
import sqlalchemy as sa


revision = "20260725_0009"
down_revision = "20260725_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("font_options") as batch:
        batch.add_column(sa.Column("pinyin", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("font_options") as batch:
        batch.drop_column("pinyin")
