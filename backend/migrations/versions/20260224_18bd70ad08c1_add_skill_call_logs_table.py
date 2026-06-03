"""add skill_call_logs table

Revision ID: 18bd70ad08c1
Revises: d11f0b4fec39
Create Date: 2026-02-24 00:58:24.501465+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18bd70ad08c1'
down_revision: Union[str, None] = 'd11f0b4fec39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.create_table(
        'skill_call_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('skill_id', sa.Integer(), nullable=True),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('tool_name', sa.String(200), nullable=False),
        sa.Column('tool_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='success'),
        sa.Column('duration_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('delete_level', sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_skill_call_logs_skill_id', 'skill_call_logs', ['skill_id'])
    op.create_index('ix_skill_call_logs_agent_id', 'skill_call_logs', ['agent_id'])
    op.create_index('ix_skill_call_logs_tool_name', 'skill_call_logs', ['tool_name'])
    op.create_index('ix_skill_call_logs_status', 'skill_call_logs', ['status'])
    op.create_index('ix_skill_call_logs_tenant_id', 'skill_call_logs', ['tenant_id'])
    op.create_index('ix_skill_call_logs_tenant_skill', 'skill_call_logs', ['tenant_id', 'skill_id'])
    op.create_index('ix_skill_call_logs_tenant_agent', 'skill_call_logs', ['tenant_id', 'agent_id'])
    op.create_index('ix_skill_call_logs_tenant_created', 'skill_call_logs', ['tenant_id', 'created_at'])


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_table('skill_call_logs')
