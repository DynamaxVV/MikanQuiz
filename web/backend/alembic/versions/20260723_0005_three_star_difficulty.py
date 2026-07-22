"""Collapse the five-star catalogue and strategy into three stars."""

import json

from alembic import op
import sqlalchemy as sa


revision = "20260723_0005"
down_revision = "20260723_0004"
branch_labels = None
depends_on = None


def _three_stars(value: int) -> int:
    return 1 if value <= 2 else 2 if value <= 4 else 3


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE questions SET difficulty = CASE WHEN difficulty <= 2 THEN 1 WHEN difficulty <= 4 THEN 2 ELSE 3 END"))
    bind.execute(sa.text("UPDATE font_options SET minimum_difficulty = CASE WHEN minimum_difficulty <= 2 THEN 1 WHEN minimum_difficulty <= 4 THEN 2 ELSE 3 END"))
    settings = bind.execute(sa.text("SELECT id, modes FROM quiz_settings")).mappings().all()
    for row in settings:
        modes = json.loads(row["modes"]) if isinstance(row["modes"], str) else row["modes"]
        collapsed = {mode: [weights[0] + weights[1], weights[2] + weights[3], weights[4]] for mode, weights in modes.items()}
        bind.execute(sa.text("UPDATE quiz_settings SET modes = :modes WHERE id = :id"), {"id": row["id"], "modes": json.dumps(collapsed)})
    with op.batch_alter_table("questions", recreate="always") as batch:
        batch.drop_constraint("ck_question_difficulty", type_="check")
        batch.create_check_constraint("ck_question_difficulty", "difficulty BETWEEN 1 AND 3")
    with op.batch_alter_table("font_options", recreate="always") as batch:
        batch.drop_constraint("ck_font_option_difficulty", type_="check")
        batch.create_check_constraint("ck_font_option_difficulty", "minimum_difficulty BETWEEN 1 AND 3")


def downgrade() -> None:
    raise RuntimeError("Three-star difficulty migration is intentionally irreversible")
