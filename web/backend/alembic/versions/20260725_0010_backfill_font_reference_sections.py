"""Backfill existing font_reference cards into a default section."""

from alembic import op
import sqlalchemy as sa


revision = "20260725_0010"
down_revision = "20260725_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    orphan_count = conn.execute(sa.text("SELECT COUNT(*) FROM font_references WHERE section_id IS NULL")).scalar()
    if not orphan_count:
        return
    existing = conn.execute(sa.text("SELECT id FROM font_reference_sections LIMIT 1")).scalar()
    if existing:
        section_id = existing
    else:
        conn.execute(sa.text("INSERT INTO font_reference_sections (name, sort_order) VALUES ('嵌字笔记', 0)"))
        section_id = conn.execute(sa.text("SELECT id FROM font_reference_sections LIMIT 1")).scalar()
    conn.execute(sa.text(f"UPDATE font_references SET section_id = {section_id}, sort_order = id WHERE section_id IS NULL"))


def downgrade() -> None:
    pass
