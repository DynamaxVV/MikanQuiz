"""Add optional font_url column to font_options."""

import sqlalchemy as sa
from alembic import op


revision = "20260725_0006"
down_revision = "20260723_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("font_options", sa.Column("font_url", sa.String(2048), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("font_options", recreate="never") as batch:
        batch.drop_column("font_url")
