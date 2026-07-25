"""Add font_reference_sections table and section support to font_references."""

from alembic import op
import sqlalchemy as sa


revision = "20260725_0008"
down_revision = "20260725_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "font_reference_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    with op.batch_alter_table("font_references") as batch:
        batch.add_column(sa.Column("section_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
        batch.create_foreign_key("fk_font_ref_section", "font_reference_sections", ["section_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("font_references") as batch:
        batch.drop_constraint("fk_font_ref_section", type_="foreignkey")
        batch.drop_column("sort_order")
        batch.drop_column("section_id")
    op.drop_table("font_reference_sections")
