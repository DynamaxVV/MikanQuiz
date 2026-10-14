"""Add optional downloadable PDF attachments to note cards."""
from alembic import op
import sqlalchemy as sa

revision = "20261014_0016"
down_revision = "20260922_0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("font_references", sa.Column("pdf_url", sa.String(2048), nullable=True))
    op.add_column("font_references", sa.Column("pdf_name", sa.String(255), nullable=False, server_default=""))
    op.add_column("font_references", sa.Column("pdf_size_bytes", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("font_references") as batch:
        batch.drop_column("pdf_size_bytes")
        batch.drop_column("pdf_name")
        batch.drop_column("pdf_url")
