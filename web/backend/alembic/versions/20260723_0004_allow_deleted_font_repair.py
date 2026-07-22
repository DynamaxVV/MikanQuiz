"""Allow catalogue deletion while leaving affected questions repairable."""

from alembic import op
import sqlalchemy as sa


revision = "20260723_0004"
down_revision = "20260723_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("questions", recreate="always") as batch:
        batch.drop_constraint("fk_questions_correct_option", type_="foreignkey")
        batch.alter_column("correct_option_id", existing_type=sa.Integer(), nullable=True)
        batch.create_foreign_key(
            "fk_questions_correct_option", "font_options", ["correct_option_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("questions", recreate="always") as batch:
        batch.drop_constraint("fk_questions_correct_option", type_="foreignkey")
        batch.alter_column("correct_option_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key("fk_questions_correct_option", "font_options", ["correct_option_id"], ["id"])
