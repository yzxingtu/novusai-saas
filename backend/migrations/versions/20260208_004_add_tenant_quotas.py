"""add tenant AI rate limits and quotas

Revision ID: 20260208_004_add_tenant_quotas
Revises: 20260208_003_add_ai_model_limits
Create Date: 2026-02-08 21:32:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260208_004_add_tenant_quotas'
down_revision = '20260208_003_add_ai_model_limits'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 tenant_model_rate_limits 表
    op.create_table(
        'tenant_model_rate_limits',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('rpm_limit', sa.Integer(), nullable=True),
        sa.Column('tpm_limit', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default='0'),
        sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], name=op.f('fk_tenant_model_rate_limits_model_id_ai_models'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tenant_model_rate_limits')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_tenant_model_rate_limits_tenant_id_tenants'), ondelete='CASCADE'),
        comment='企业 AI 模型速率限制配置'
    )
    
    # 创建索引
    op.create_index(op.f('ix_tenant_model_rate_limits_tenant_id'), 'tenant_model_rate_limits', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_tenant_model_rate_limits_model_id'), 'tenant_model_rate_limits', ['model_id'], unique=False)
    op.create_index(op.f('ix_tenant_model_rate_limits_is_active'), 'tenant_model_rate_limits', ['is_active'], unique=False)
    op.create_index(op.f('ix_tenant_model_rate_limits_created_at'), 'tenant_model_rate_limits', ['created_at'], unique=False)
    
    # 创建 tenant_quotas 表
    op.create_table(
        'tenant_quotas',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=True),
        sa.Column('period', sa.String(length=20), nullable=False, server_default='monthly'),
        sa.Column('limit', sa.Integer(), nullable=False),
        sa.Column('quota_type', sa.String(length=20), nullable=False, server_default='soft'),
        sa.Column('warning_threshold', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default='0'),
        sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], name=op.f('fk_tenant_quotas_model_id_ai_models'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tenant_quotas')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_tenant_quotas_tenant_id_tenants'), ondelete='CASCADE'),
        comment='企业 AI 配额配置'
    )
    
    # 创建索引
    op.create_index(op.f('ix_tenant_quotas_tenant_id'), 'tenant_quotas', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_tenant_quotas_model_id'), 'tenant_quotas', ['model_id'], unique=False)
    op.create_index(op.f('ix_tenant_quotas_period'), 'tenant_quotas', ['period'], unique=False)
    op.create_index(op.f('ix_tenant_quotas_quota_type'), 'tenant_quotas', ['quota_type'], unique=False)
    op.create_index(op.f('ix_tenant_quotas_is_active'), 'tenant_quotas', ['is_active'], unique=False)
    op.create_index(op.f('ix_tenant_quotas_created_at'), 'tenant_quotas', ['created_at'], unique=False)


def downgrade() -> None:
    # 删除索引
    op.drop_index(op.f('ix_tenant_quotas_created_at'), table_name='tenant_quotas')
    op.drop_index(op.f('ix_tenant_quotas_is_active'), table_name='tenant_quotas')
    op.drop_index(op.f('ix_tenant_quotas_quota_type'), table_name='tenant_quotas')
    op.drop_index(op.f('ix_tenant_quotas_period'), table_name='tenant_quotas')
    op.drop_index(op.f('ix_tenant_quotas_model_id'), table_name='tenant_quotas')
    op.drop_index(op.f('ix_tenant_quotas_tenant_id'), table_name='tenant_quotas')
    
    # 删除表
    op.drop_table('tenant_quotas')
    
    # 删除索引
    op.drop_index(op.f('ix_tenant_model_rate_limits_created_at'), table_name='tenant_model_rate_limits')
    op.drop_index(op.f('ix_tenant_model_rate_limits_is_active'), table_name='tenant_model_rate_limits')
    op.drop_index(op.f('ix_tenant_model_rate_limits_model_id'), table_name='tenant_model_rate_limits')
    op.drop_index(op.f('ix_tenant_model_rate_limits_tenant_id'), table_name='tenant_model_rate_limits')
    
    # 删除表
    op.drop_table('tenant_model_rate_limits')
