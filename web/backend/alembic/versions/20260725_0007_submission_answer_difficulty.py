"""Add difficulty column to submission_answers."""

import sqlalchemy as sa
from alembic import op


revision = "20260725_0007"
down_revision = "04566e2d321a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submission_answers", sa.Column("difficulty", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    with op.batch_alter_table("submission_answers", recreate="never") as batch:
        batch.drop_column("difficulty")
