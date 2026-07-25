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
    # Migrate existing cards into a default section
    conn = op.get_bind()
    has_rows = conn.execute(sa.text("SELECT COUNT(*) FROM font_references")).scalar()
    if has_rows:
        conn.execute(sa.text("INSERT INTO font_reference_sections (name, sort_order) VALUES ('嵌字笔记', 0)"))
        section_id = conn.execute(sa.text("SELECT id FROM font_reference_sections LIMIT 1")).scalar()
        conn.execute(sa.text(f"UPDATE font_references SET section_id = {section_id}, sort_order = id WHERE section_id IS NULL"))


def downgrade() -> None:
    with op.batch_alter_table("font_references") as batch:
        batch.drop_constraint("fk_font_ref_section", type_="foreignkey")
        batch.drop_column("sort_order")
        batch.drop_column("section_id")
    op.drop_table("font_reference_sections")
