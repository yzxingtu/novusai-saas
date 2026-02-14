"""add ai_query_logs table

Revision ID: 6f8e790c9a68
Revises: 20a20a8194e9
Create Date: 2026-02-12 16:37:18.719450+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6f8e790c9a68'
down_revision: Union[str, None] = '20a20a8194e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.create_table('ai_query_logs',
    sa.Column('agent_id', sa.Integer(), nullable=True, comment='智能体 ID'),
    sa.Column('user_id', sa.Integer(), nullable=True, comment='操作者 ID'),
    sa.Column('user_role', sa.String(length=50), nullable=False, comment='操作者角色'),
    sa.Column('question', sa.Text(), nullable=False, comment='查询问题'),
    sa.Column('generated_sql', sa.Text(), nullable=True, comment='生成的 SQL'),
    sa.Column('final_sql', sa.Text(), nullable=True, comment='最终执行的 SQL'),
    sa.Column('row_count', sa.Integer(), nullable=True, comment='返回行数'),
    sa.Column('status', sa.String(length=50), nullable=False, comment='执行状态'),
    sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息'),
    sa.Column('duration_ms', sa.Integer(), nullable=True, comment='执行耗时(ms)'),
    sa.Column('confidence', sa.String(length=20), nullable=True, comment='置信度'),
    sa.Column('tenant_id', sa.Integer(), nullable=False, comment='租户ID'),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
    sa.Column('is_deleted', sa.Boolean(), nullable=False, comment='软删除标记'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ai_query_logs_status_created', 'ai_query_logs', ['status', 'created_at'], unique=False)
    op.create_index('idx_ai_query_logs_tenant_created', 'ai_query_logs', ['tenant_id', 'created_at'], unique=False)
    op.create_index('idx_ai_query_logs_user_created', 'ai_query_logs', ['user_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_ai_query_logs_agent_id'), 'ai_query_logs', ['agent_id'], unique=False)
    op.create_index(op.f('ix_ai_query_logs_id'), 'ai_query_logs', ['id'], unique=False)
    op.create_index(op.f('ix_ai_query_logs_is_deleted'), 'ai_query_logs', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_ai_query_logs_status'), 'ai_query_logs', ['status'], unique=False)
    op.create_index(op.f('ix_ai_query_logs_tenant_id'), 'ai_query_logs', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_ai_query_logs_user_id'), 'ai_query_logs', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index(op.f('ix_ai_query_logs_user_id'), table_name='ai_query_logs')
    op.drop_index(op.f('ix_ai_query_logs_tenant_id'), table_name='ai_query_logs')
    op.drop_index(op.f('ix_ai_query_logs_status'), table_name='ai_query_logs')
    op.drop_index(op.f('ix_ai_query_logs_is_deleted'), table_name='ai_query_logs')
    op.drop_index(op.f('ix_ai_query_logs_id'), table_name='ai_query_logs')
    op.drop_index(op.f('ix_ai_query_logs_agent_id'), table_name='ai_query_logs')
    op.drop_index('idx_ai_query_logs_user_created', table_name='ai_query_logs')
    op.drop_index('idx_ai_query_logs_tenant_created', table_name='ai_query_logs')
    op.drop_index('idx_ai_query_logs_status_created', table_name='ai_query_logs')
    op.drop_table('ai_query_logs')
