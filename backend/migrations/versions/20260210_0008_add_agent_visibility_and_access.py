# -*- coding: utf-8 -*-
"""add agent visibility and agent_access table

Revision ID: 20260210_0008
Revises: 20260210_0007
Create Date: 2026-02-10 14:40:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260210_0008'
down_revision: Union[str, None] = '20260210_0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add visibility column to agents; create agent_access table."""

    # 1. agents 表新增 visibility 字段
    op.add_column(
        'agents',
        sa.Column('visibility', sa.String(20), nullable=False, server_default='public'),
    )
    op.create_index('ix_agents_visibility', 'agents', ['visibility'])

    # 2. 创建 agent_access 表
    op.create_table(
        'agent_access',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('access_type', sa.String(20), nullable=False, server_default='all_users'),
        sa.Column('org_node_ids', sa.JSON(), nullable=True),
        sa.Column('user_ids', sa.JSON(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indexes
    op.create_index('ix_agent_access_tenant_id', 'agent_access', ['tenant_id'])
    op.create_index(
        'ix_agent_access_tenant_agent',
        'agent_access',
        ['tenant_id', 'agent_id'],
        unique=True,
    )


def downgrade() -> None:
    """Drop agent_access table; remove visibility column from agents."""
    op.drop_index('ix_agent_access_tenant_agent', table_name='agent_access')
    op.drop_index('ix_agent_access_tenant_id', table_name='agent_access')
    op.drop_table('agent_access')

    op.drop_index('ix_agents_visibility', table_name='agents')
    op.drop_column('agents', 'visibility')
