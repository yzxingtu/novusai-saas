"""add AI usage stats table

Revision ID: 20260207_002_add_ai_usage_stats
Revises: 20260120_001_add_ai_providers

Create Date: 2026-02-08 05:52:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260207_002_add_ai_usage_stats'
down_revision = '20260120_001_add_ai_providers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 ai_usage_stats 表
    op.create_table(
        'ai_usage_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('request_type', sa.String(length=50), nullable=False, server_default='chat'),
        sa.Column('stat_date', sa.Date(), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('call_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_cost', sa.Numeric(precision=10, scale=6), nullable=False, server_default='0'),
        sa.Column('avg_latency_ms', sa.Integer(), nullable=True),
        sa.Column('max_latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], name='fk_ai_usage_stats_model_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'user_id', 'model_id', 'request_type', 'stat_date',
            name='uq_ai_usage_stat_dims'
        )
    )
    
    # 创建索引
    op.create_index('ix_ai_usage_stats_id', 'ai_usage_stats', ['id'])
    op.create_index('ix_ai_usage_stats_tenant_id', 'ai_usage_stats', ['tenant_id'])
    op.create_index('ix_ai_usage_stats_user_id', 'ai_usage_stats', ['user_id'])
    op.create_index('ix_ai_usage_stats_model_id', 'ai_usage_stats', ['model_id'])
    op.create_index('ix_ai_usage_stats_request_type', 'ai_usage_stats', ['request_type'])
    op.create_index('ix_ai_usage_stats_stat_date', 'ai_usage_stats', ['stat_date'])
    op.create_index('ix_ai_usage_stats_total_tokens', 'ai_usage_stats', ['total_tokens'])
    op.create_index('ix_ai_usage_stats_call_count', 'ai_usage_stats', ['call_count'])
    op.create_index('ix_ai_usage_stats_total_cost', 'ai_usage_stats', ['total_cost'])
    
    # 创建复合索引
    op.create_index('idx_ai_usage_stats_tenant_date', 'ai_usage_stats', ['tenant_id', 'stat_date'])
    op.create_index('idx_ai_usage_stats_user_date', 'ai_usage_stats', ['user_id', 'stat_date'])
    op.create_index('idx_ai_usage_stats_model_date', 'ai_usage_stats', ['model_id', 'stat_date'])


def downgrade() -> None:
    # 删除索引
    op.drop_index('idx_ai_usage_stats_model_date', table_name='ai_usage_stats')
    op.drop_index('idx_ai_usage_stats_user_date', table_name='ai_usage_stats')
    op.drop_index('idx_ai_usage_stats_tenant_date', table_name='ai_usage_stats')
    op.drop_index('ix_ai_usage_stats_total_cost', table_name='ai_usage_stats')
    op.drop_index('ix_ai_usage_stats_call_count', table_name='ai_usage_stats')
    op.drop_index('ix_ai_usage_stats_total_tokens', table_name='ai_usage_stats')
    op.drop_index('ix_ai_usage_stats_stat_date', table_name='ai_usage_stats')
    op.drop_index('ix_ai_usage_stats_request_type', table_name='ai_usage_stats')
    op.drop_index('ix_ai_usage_stats_model_id', table_name='ai_usage_stats')
    op.drop_index('ix_ai_usage_stats_user_id', table_name='ai_usage_stats')
    op.drop_index('ix_ai_usage_stats_tenant_id', table_name='ai_usage_stats')
    op.drop_index('ix_ai_usage_stats_id', table_name='ai_usage_stats')
    
    # 删除表
    op.drop_table('ai_usage_stats')
