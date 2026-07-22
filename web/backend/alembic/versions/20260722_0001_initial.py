"""Create the standalone quiz backend schema and seed its singleton settings."""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260722_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all first-release tables without relying on application startup."""
    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("legacy_id", sa.String(length=128), unique=True, nullable=True),
        sa.Column("text", sa.String(length=500), nullable=False),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("option_a", sa.String(length=500), nullable=False),
        sa.Column("option_b", sa.String(length=500), nullable=False),
        sa.Column("option_c", sa.String(length=500), nullable=False),
        sa.Column("option_d", sa.String(length=500), nullable=False),
        sa.Column("answer", sa.String(length=1), nullable=False),
        sa.Column("explanation", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_question_difficulty"),
        sa.CheckConstraint("answer IN ('A', 'B', 'C', 'D')", name="ck_question_answer"),
    )
    op.create_index("ix_questions_difficulty", "questions", ["difficulty"])
    op.create_table(
        "quiz_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("modes", sa.JSON(), nullable=False),
        sa.Column("font_presets", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_settings_singleton"),
    )
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admins.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(length=64), unique=True, nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("question_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_quiz_attempts_expires_at", "quiz_attempts", ["expires_at"])
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("quiz_attempts.id"), nullable=False),
        sa.Column("display_name", sa.String(length=20), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("attempt_id", name="uq_submission_attempt"),
    )
    op.create_index("ix_submissions_submitted_at", "submissions", ["submitted_at"])
    op.create_table(
        "submission_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "submission_id",
            sa.Integer(),
            sa.ForeignKey("submissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            sa.Integer(),
            sa.ForeignKey("questions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("question_text", sa.String(length=500), nullable=False),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("selected", sa.String(length=1), nullable=False),
        sa.Column("correct_answer", sa.String(length=1), nullable=False),
        sa.Column("explanation", sa.String(length=1000), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
    )
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO quiz_settings "
            "(id, question_count, modes, font_presets, updated_at) "
            "VALUES (:id, :count, :modes, :fonts, :now)"
        ),
        {
            "id": 1,
            "count": 10,
            "modes": '{"beginner":[65,25,10,0,0],"proficient":[15,25,30,20,10],"challenge":[0,10,20,30,40]}',
            "fonts": "[]",
            "now": datetime.now(timezone.utc),
        },
    )


def downgrade() -> None:
    """Drop tables in dependency order for an intentionally destructive downgrade."""
    op.drop_table("submission_answers")
    op.drop_index("ix_submissions_submitted_at", table_name="submissions")
    op.drop_table("submissions")
    op.drop_index("ix_quiz_attempts_expires_at", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
    op.drop_index("ix_admin_sessions_expires_at", table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_table("admins")
    op.drop_table("quiz_settings")
    op.drop_index("ix_questions_difficulty", table_name="questions")
    op.drop_table("questions")
