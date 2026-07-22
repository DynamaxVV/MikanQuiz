"""Replace fixed A-D questions with reusable grouped font options."""

from alembic import op
import sqlalchemy as sa


revision = "20260723_0003"
down_revision = "20260722_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "option_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "font_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("option_groups.id"), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("minimum_difficulty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("minimum_difficulty BETWEEN 1 AND 5", name="ck_font_option_difficulty"),
    )
    bind = op.get_bind()
    groups = ["类黑体", "类宋体", "类圆体", "其他"]
    for index, name in enumerate(groups):
        bind.execute(sa.text("INSERT INTO option_groups (name, sort_order) VALUES (:name, :sort_order)"), {"name": name, "sort_order": index})
    other_id = bind.execute(sa.text("SELECT id FROM option_groups WHERE name = '其他'")).scalar_one()
    rows = bind.execute(sa.text("SELECT id, option_a, option_b, option_c, option_d, answer FROM questions")).mappings().all()
    option_ids: dict[str, int] = {}
    for row in rows:
        for index, name in enumerate((row["option_a"], row["option_b"], row["option_c"], row["option_d"])):
            if name not in option_ids:
                result = bind.execute(sa.text("INSERT INTO font_options (group_id, name, minimum_difficulty, sort_order) VALUES (:group_id, :name, 1, :sort_order)"), {"group_id": other_id, "name": name, "sort_order": len(option_ids)})
                option_ids[name] = result.lastrowid
    op.add_column("questions", sa.Column("correct_option_id", sa.Integer(), nullable=True))
    for row in rows:
        answer_index = ord(row["answer"]) - ord("A")
        name = (row["option_a"], row["option_b"], row["option_c"], row["option_d"])[answer_index]
        bind.execute(sa.text("UPDATE questions SET correct_option_id = :option_id WHERE id = :question_id"), {"option_id": option_ids[name], "question_id": row["id"]})
    with op.batch_alter_table("questions", recreate="always") as batch:
        batch.drop_constraint("ck_question_answer", type_="check")
        batch.drop_column("option_a")
        batch.drop_column("option_b")
        batch.drop_column("option_c")
        batch.drop_column("option_d")
        batch.drop_column("answer")
        batch.alter_column("correct_option_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key("fk_questions_correct_option", "font_options", ["correct_option_id"], ["id"])
    op.add_column("quiz_attempts", sa.Column("question_snapshots", sa.JSON(), nullable=True))
    bind.execute(sa.text("DELETE FROM quiz_attempts WHERE submitted_at IS NULL"))
    bind.execute(sa.text("UPDATE quiz_attempts SET question_snapshots = '[]' WHERE question_snapshots IS NULL"))
    with op.batch_alter_table("quiz_attempts", recreate="always") as batch:
        batch.alter_column("question_snapshots", existing_type=sa.JSON(), nullable=False)
    op.add_column("submission_answers", sa.Column("option_groups", sa.JSON(), nullable=True))
    op.add_column("submission_answers", sa.Column("selected_option_id", sa.Integer(), nullable=True))
    op.add_column("submission_answers", sa.Column("correct_option_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("submission_answers", recreate="always") as batch:
        batch.alter_column("selected", existing_type=sa.String(length=1), type_=sa.String(length=64), nullable=False)
        batch.alter_column("correct_answer", existing_type=sa.String(length=1), type_=sa.String(length=64), nullable=False)


def downgrade() -> None:
    raise RuntimeError("Option catalogue migration is intentionally irreversible")
