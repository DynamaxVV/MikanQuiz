"""add_difficulty_to_font_references

Revision ID: 04566e2d321a
Revises: 20260725_0006
Create Date: 2026-07-25 04:06:37.869962
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '04566e2d321a'
down_revision = '20260725_0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("font_references", sa.Column("difficulty", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("font_references", "difficulty")
