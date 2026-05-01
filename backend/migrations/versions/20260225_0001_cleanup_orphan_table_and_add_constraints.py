"""cleanup: drop orphan table, add constraints, fix column drift

Revision ID: 20260225_0001
Revises: kb_attachment_null_tid
Create Date: 2026-02-25

Cleanup items:
1. Drop orphaned crud_generation_records table (model deleted, zero code references)
"""

from alembic import op
import sqlalchemy as sa

revision = '20260225_0001'
down_revision = 'kb_attachment_null_tid'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop orphaned table if it still exists (model was deleted during toolkit refactor)
    op.execute(sa.text("DROP TABLE IF EXISTS crud_generation_records CASCADE"))


def downgrade() -> None:
    # Recreate crud_generation_records (minimal schema for rollback)
    op.create_table(
        'crud_generation_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('table_name', sa.String(200), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('generated_code', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('delete_level', sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
