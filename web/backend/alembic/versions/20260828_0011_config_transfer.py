"""Add stable configuration keys and durable JSON sync outbox state."""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "20260828_0011"
down_revision = "20260725_0010"
branch_labels = None
depends_on = None


ROLE_KEYS = {
    "black": "system.option-group.black",
    "song": "system.option-group.song",
    "round": "system.option-group.round",
}
ROLE_ALIASES = {
    "black": {"类黑", "类黑体", "黑体"},
    "song": {"类宋", "类宋体", "宋体"},
    "round": {"类圆", "类圆体", "圆体"},
}


def _backfill_keys(bind: sa.Connection, table: str) -> None:
    rows = bind.execute(sa.text(f"SELECT id FROM {table} WHERE config_key IS NULL ORDER BY id")).all()
    for (row_id,) in rows:
        bind.execute(
            sa.text(f"UPDATE {table} SET config_key = :key WHERE id = :id"),
            {"key": str(uuid4()), "id": row_id},
        )


def upgrade() -> None:
    bind = op.get_bind()
    for table in ("option_groups", "font_options", "questions", "font_reference_sections", "font_references"):
        op.add_column(table, sa.Column("config_key", sa.String(length=64), nullable=True))

    groups = bind.execute(sa.text("SELECT id, name FROM option_groups ORDER BY id")).mappings().all()
    for role, aliases in ROLE_ALIASES.items():
        candidates = [row for row in groups if row["name"].strip() in aliases]
        if len(candidates) != 1:
            raise RuntimeError(f"无法唯一识别系统分区 {role}，候选数量为 {len(candidates)}")
        bind.execute(
            sa.text("UPDATE option_groups SET config_key = :key WHERE id = :id"),
            {"key": ROLE_KEYS[role], "id": candidates[0]["id"]},
        )
    _backfill_keys(bind, "option_groups")
    for table in ("font_options", "questions", "font_reference_sections", "font_references"):
        _backfill_keys(bind, table)

    for table in ("option_groups", "font_options", "questions", "font_reference_sections", "font_references"):
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.alter_column("config_key", existing_type=sa.String(length=64), nullable=False)
        op.create_index(f"uq_{table}_config_key", table, ["config_key"], unique=True)

    op.create_table(
        "sync_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_token", sa.String(length=64), nullable=True),
        sa.Column("scope_fence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope", "state_hash", name="uq_sync_outbox_scope_hash"),
    )
    op.create_index("ix_sync_outbox_claim", "sync_outbox", ["status", "available_at"])
    op.create_table(
        "sync_scope_state",
        sa.Column("scope", sa.String(length=32), primary_key=True),
        sa.Column("current_state_hash", sa.String(length=64), nullable=True),
        sa.Column("published_state_hash", sa.String(length=64), nullable=True),
        sa.Column("fence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_index("ix_sync_outbox_claim", table_name="sync_outbox")
    op.drop_table("sync_scope_state")
    op.drop_table("sync_outbox")
    for table in ("font_references", "font_reference_sections", "questions", "font_options", "option_groups"):
        op.drop_index(f"uq_{table}_config_key", table_name=table)
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.drop_column("config_key")
