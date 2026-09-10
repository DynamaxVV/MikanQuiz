"""Add durable batch question creation receipts."""
from alembic import op
import sqlalchemy as sa

revision = '20260909_0012'
down_revision = '20260828_0011'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('question_requests',
        sa.Column('admin_id', sa.Integer(), sa.ForeignKey('admins.id'), primary_key=True),
        sa.Column('request_id', sa.String(64), primary_key=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('question_key', sa.String(64), nullable=True),
    )


def downgrade():
    op.drop_table('question_requests')
