"""add ai_action_logs table

Revision ID: ee87f790553e
Revises: 20260210_0009
Create Date: 2026-02-11 15:29:47.518054+00:00

NOTE: Original autogenerate output contained ~600 lines of unrelated alter_column
noise (comment/server_default changes on agent_access, agent_conversations, agents,
batch_runs, conversation_messages, tool_definitions, etc.). Cleaned up to keep only
the ai_action_logs table creation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ee87f790553e'
down_revision: Union[str, None] = '20260210_0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ai_action_logs',
    sa.Column('agent_id', sa.Integer(), nullable=False, comment='智能体 ID'),
    sa.Column('conversation_id', sa.Integer(), nullable=True, comment='对话 ID'),
    sa.Column('operator_id', sa.Integer(), nullable=True, comment='操作者 ID'),
    sa.Column('action_name', sa.String(length=100), nullable=False, comment='操作名称'),
    sa.Column('action_type', sa.String(length=50), nullable=False, comment='操作类型'),
    sa.Column('action_level', sa.String(length=50), nullable=False, comment='安全等级'),
    sa.Column('request_data', sa.JSON(), nullable=True, comment='请求数据'),
    sa.Column('response_data', sa.JSON(), nullable=True, comment='响应数据'),
    sa.Column('status', sa.String(length=50), nullable=False, comment='执行状态'),
    sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息'),
    sa.Column('duration_ms', sa.Integer(), nullable=True, comment='执行耗时（毫秒）'),
    sa.Column('tenant_id', sa.Integer(), nullable=False, comment='企业ID'),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
    sa.Column('is_deleted', sa.Boolean(), nullable=False, comment='软删除标记'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ai_action_logs_operator_created', 'ai_action_logs', ['operator_id', 'created_at'], unique=False)
    op.create_index('idx_ai_action_logs_tenant_created', 'ai_action_logs', ['tenant_id', 'created_at'], unique=False)
    op.create_index('idx_ai_action_logs_type_created', 'ai_action_logs', ['action_type', 'created_at'], unique=False)
    op.create_index(op.f('ix_ai_action_logs_action_name'), 'ai_action_logs', ['action_name'], unique=False)
    op.create_index(op.f('ix_ai_action_logs_agent_id'), 'ai_action_logs', ['agent_id'], unique=False)
    op.create_index(op.f('ix_ai_action_logs_conversation_id'), 'ai_action_logs', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_ai_action_logs_id'), 'ai_action_logs', ['id'], unique=False)
    op.create_index(op.f('ix_ai_action_logs_is_deleted'), 'ai_action_logs', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_ai_action_logs_operator_id'), 'ai_action_logs', ['operator_id'], unique=False)
    op.create_index(op.f('ix_ai_action_logs_status'), 'ai_action_logs', ['status'], unique=False)
    op.create_index(op.f('ix_ai_action_logs_tenant_id'), 'ai_action_logs', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_ai_action_logs_type_created', table_name='ai_action_logs')
    op.drop_index('idx_ai_action_logs_tenant_created', table_name='ai_action_logs')
    op.drop_index('idx_ai_action_logs_operator_created', table_name='ai_action_logs')
    op.drop_index(op.f('ix_ai_action_logs_tenant_id'), table_name='ai_action_logs')
    op.drop_index(op.f('ix_ai_action_logs_status'), table_name='ai_action_logs')
    op.drop_index(op.f('ix_ai_action_logs_operator_id'), table_name='ai_action_logs')
    op.drop_index(op.f('ix_ai_action_logs_is_deleted'), table_name='ai_action_logs')
    op.drop_index(op.f('ix_ai_action_logs_id'), table_name='ai_action_logs')
    op.drop_index(op.f('ix_ai_action_logs_conversation_id'), table_name='ai_action_logs')
    op.drop_index(op.f('ix_ai_action_logs_agent_id'), table_name='ai_action_logs')
    op.drop_index(op.f('ix_ai_action_logs_action_name'), table_name='ai_action_logs')
    op.drop_table('ai_action_logs')
