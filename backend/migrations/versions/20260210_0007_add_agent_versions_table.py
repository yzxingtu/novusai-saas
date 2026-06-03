# -*- coding: utf-8 -*-
"""add agent_versions table

Revision ID: 20260210_0007
Revises: 20260210_0006
Create Date: 2026-02-10 13:55:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260210_0007'
down_revision: Union[str, None] = '20260210_0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent_versions table for version snapshots."""
    op.create_table(
        'agent_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('model_id', sa.Integer(), sa.ForeignKey('ai_models.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('top_p', sa.Float(), nullable=True),
        sa.Column('execution_mode', sa.String(20), nullable=False),
        sa.Column('skill_grant_snapshot', sa.JSON(), nullable=True),
        sa.Column('input_variables', sa.JSON(), nullable=True),
        sa.Column('welcome_message', sa.Text(), nullable=True),
        sa.Column('suggested_questions', sa.JSON(), nullable=True),
        sa.Column('quota_config', sa.JSON(), nullable=True),
        sa.Column('change_log', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_id', 'version', name='uq_agent_version'),
    )

    # Indexes
    op.create_index('ix_agent_versions_tenant_id', 'agent_versions', ['tenant_id'])
    op.create_index('ix_agent_versions_agent_id', 'agent_versions', ['agent_id'])
    op.create_index('ix_agent_versions_agent_version', 'agent_versions', ['agent_id', 'version'])


def downgrade() -> None:
    """Drop agent_versions table."""
    op.drop_index('ix_agent_versions_agent_version', table_name='agent_versions')
    op.drop_index('ix_agent_versions_agent_id', table_name='agent_versions')
    op.drop_index('ix_agent_versions_tenant_id', table_name='agent_versions')
    op.drop_table('agent_versions')
