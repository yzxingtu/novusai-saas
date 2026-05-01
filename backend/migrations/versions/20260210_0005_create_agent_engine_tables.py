# -*- coding: utf-8 -*-
"""create agent engine base tables

Creates the base tables required by the AI Agent Engine:
- agents: 智能体主表
- agent_conversations: 智能体对话表
- conversation_messages: 对话消息表
- batch_runs: 批量执行记录表

Revision ID: 20260210_0005
Revises: 147c588d9898
Create Date: 2026-02-10 16:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260210_0005'
down_revision: Union[str, None] = '147c588d9898'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ========== 1. agents 表 ==========
    # 注意: quota_config 由 0006 追加, visibility 由 0008 追加,
    #       context_config / output_schema 由 0009 追加
    op.create_table(
        'agents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        # 基本信息
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('avatar', sa.String(255), nullable=True),
        # 模型配置
        sa.Column('model_id', sa.Integer(), sa.ForeignKey('ai_models.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('top_p', sa.Float(), nullable=True),
        # 状态与模式
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('execution_mode', sa.String(20), nullable=False, server_default='conversation'),
        sa.Column('published_version', sa.Integer(), nullable=True),
        # 变量
        sa.Column('input_variables', sa.JSON(), nullable=True),
        # 交互配置
        sa.Column('welcome_message', sa.Text(), nullable=True),
        sa.Column('suggested_questions', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_agents_tenant_id', 'agents', ['tenant_id'])
    op.create_index('ix_agents_name', 'agents', ['name'])
    op.create_index('ix_agents_model_id', 'agents', ['model_id'])
    op.create_index('ix_agents_status', 'agents', ['status'])
    op.create_index('ix_agents_is_deleted', 'agents', ['is_deleted'])
    op.create_index('ix_agents_tenant_status', 'agents', ['tenant_id', 'status'])

    # ========== 2. agent_conversations 表 ==========
    op.create_table(
        'agent_conversations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        # 关联
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        # 基本信息
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        # 消息存储 (初版 JSON, 后续迁移至独立模型)
        sa.Column('messages', sa.JSON(), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        # 消耗统计
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost', sa.Numeric(12, 6), nullable=False, server_default='0'),
        # 扩展
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_agent_conv_tenant_id', 'agent_conversations', ['tenant_id'])
    op.create_index('ix_agent_conv_agent_id', 'agent_conversations', ['agent_id'])
    op.create_index('ix_agent_conv_user_id', 'agent_conversations', ['user_id'])
    op.create_index('ix_agent_conv_status', 'agent_conversations', ['status'])
    op.create_index('ix_agent_conv_is_deleted', 'agent_conversations', ['is_deleted'])
    op.create_index('ix_agent_conv_tenant_agent_user', 'agent_conversations', ['tenant_id', 'agent_id', 'user_id'])

    # ========== 3. conversation_messages 表 ==========
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        # 关联
        sa.Column('conversation_id', sa.Integer(), sa.ForeignKey('agent_conversations.id', ondelete='CASCADE'), nullable=False),
        # 消息内容
        sa.Column('role', sa.String(20), nullable=False, server_default='user'),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='0'),
        # Token 统计
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
        # Function Calling
        sa.Column('tool_calls', sa.JSON(), nullable=True),
        sa.Column('tool_call_id', sa.String(100), nullable=True),
        sa.Column('tool_name', sa.String(100), nullable=True),
        # 性能指标
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        # 关联模型
        sa.Column('model_id', sa.Integer(), sa.ForeignKey('ai_models.id', ondelete='SET NULL'), nullable=True),
        # 扩展
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_conv_msg_tenant_id', 'conversation_messages', ['tenant_id'])
    op.create_index('ix_conv_msg_conversation_id', 'conversation_messages', ['conversation_id'])
    op.create_index('ix_conv_msg_role', 'conversation_messages', ['role'])
    op.create_index('ix_conv_msg_is_deleted', 'conversation_messages', ['is_deleted'])
    op.create_index('ix_conv_msg_conv_seq', 'conversation_messages', ['conversation_id', 'sequence'])
    op.create_index('ix_conv_msg_tenant_conv', 'conversation_messages', ['tenant_id', 'conversation_id'])

    # ========== 4. batch_runs 表 ==========
    op.create_table(
        'batch_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        # 关联
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        # 状态
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        # 进度
        sa.Column('total_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_workers', sa.Integer(), nullable=False, server_default='5'),
        # 结果
        sa.Column('results', sa.JSON(), nullable=True),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('input_items', sa.JSON(), nullable=True),
        # Celery
        sa.Column('celery_task_id', sa.String(64), nullable=True),
        # 时间
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('ix_batch_runs_tenant_id', 'batch_runs', ['tenant_id'])
    op.create_index('ix_batch_runs_agent_id', 'batch_runs', ['agent_id'])
    op.create_index('ix_batch_runs_status', 'batch_runs', ['status'])
    op.create_index('ix_batch_runs_is_deleted', 'batch_runs', ['is_deleted'])
    op.create_index('ix_batch_runs_tenant_agent', 'batch_runs', ['tenant_id', 'agent_id'])
    op.create_index('ix_batch_runs_tenant_status', 'batch_runs', ['tenant_id', 'status'])


def downgrade() -> None:
    # Drop in reverse order of creation (respect FK dependencies)
    op.drop_table('batch_runs')
    op.drop_table('conversation_messages')
    op.drop_table('agent_conversations')
    op.drop_table('agents')
