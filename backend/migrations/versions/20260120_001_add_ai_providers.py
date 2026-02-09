"""add AI provider models

Revision ID: 20260120_add_ai_provider_models
Revises: 676cbd976326
Create Date: 2026-02-08 04:54:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260120_001_add_ai_providers'
down_revision = '676cbd976326'  # 接在最新的迁移版本之后
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 ai_providers 表
    op.create_table(
        'ai_providers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('base_url', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('config', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_providers_id', 'ai_providers', ['id'])
    op.create_index('ix_ai_providers_code', 'ai_providers', ['code'], unique=True)
    op.create_index('ix_ai_providers_name', 'ai_providers', ['name'])
    op.create_index('ix_ai_providers_is_active', 'ai_providers', ['is_active'])
    
    # 创建 ai_models 表
    op.create_table(
        'ai_models',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('context_window', sa.Integer(), nullable=True),
        sa.Column('max_output_tokens', sa.Integer(), nullable=True),
        sa.Column('input_price_per_1k', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('output_price_per_1k', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('supports_function_calling', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('supports_vision', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('supports_streaming', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('config', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['provider_id'], ['ai_providers.id'], name='fk_ai_models_provider_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_models_id', 'ai_models', ['id'])
    op.create_index('ix_ai_models_code', 'ai_models', ['code'], unique=True)
    op.create_index('ix_ai_models_name', 'ai_models', ['name'])
    op.create_index('ix_ai_models_provider_id', 'ai_models', ['provider_id'])
    op.create_index('ix_ai_models_is_active', 'ai_models', ['is_active'])
    
    # 创建 ai_api_keys 表
    op.create_table(
        'ai_api_keys',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('encrypted_key', sa.String(length=500), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('usage_limit', sa.Integer(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['provider_id'], ['ai_providers.id'], name='fk_ai_api_keys_provider_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_ai_api_keys_tenant_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_api_keys_id', 'ai_api_keys', ['id'])
    op.create_index('ix_ai_api_keys_provider_id', 'ai_api_keys', ['provider_id'])
    op.create_index('ix_ai_api_keys_tenant_id', 'ai_api_keys', ['tenant_id'])
    op.create_index('ix_ai_api_keys_is_active', 'ai_api_keys', ['is_active'])
    
    # 创建 ai_call_logs 表
    op.create_table(
        'ai_call_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('user_type', sa.String(length=50), nullable=True),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('request_type', sa.String(length=50), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('cost', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('request_hash', sa.String(length=64), nullable=True),
        sa.Column('metadata', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['provider_id'], ['ai_providers.id'], name='fk_ai_call_logs_provider_id', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['model_id'], ['ai_models.id'], name='fk_ai_call_logs_model_id', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_call_logs_id', 'ai_call_logs', ['id'])
    op.create_index('ix_ai_call_logs_tenant_id', 'ai_call_logs', ['tenant_id'])
    op.create_index('ix_ai_call_logs_user_id', 'ai_call_logs', ['user_id'])
    op.create_index('ix_ai_call_logs_provider_id', 'ai_call_logs', ['provider_id'])
    op.create_index('ix_ai_call_logs_model_id', 'ai_call_logs', ['model_id'])
    op.create_index('ix_ai_call_logs_request_type', 'ai_call_logs', ['request_type'])
    op.create_index('ix_ai_call_logs_status', 'ai_call_logs', ['status'])
    op.create_index('ix_ai_call_logs_total_tokens', 'ai_call_logs', ['total_tokens'])
    op.create_index('ix_ai_call_logs_request_hash', 'ai_call_logs', ['request_hash'])
    op.create_index('idx_ai_call_logs_tenant_created', 'ai_call_logs', ['tenant_id', 'created_at'])
    op.create_index('idx_ai_call_logs_user_status', 'ai_call_logs', ['user_id', 'status'])
    op.create_index('idx_ai_call_logs_model_created', 'ai_call_logs', ['model_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('idx_ai_call_logs_model_created', table_name='ai_call_logs')
    op.drop_index('idx_ai_call_logs_user_status', table_name='ai_call_logs')
    op.drop_index('idx_ai_call_logs_tenant_created', table_name='ai_call_logs')
    op.drop_index('ix_ai_call_logs_request_hash', table_name='ai_call_logs')
    op.drop_index('ix_ai_call_logs_total_tokens', table_name='ai_call_logs')
    op.drop_index('ix_ai_call_logs_status', table_name='ai_call_logs')
    op.drop_index('ix_ai_call_logs_request_type', table_name='ai_call_logs')
    op.drop_index('ix_ai_call_logs_model_id', table_name='ai_call_logs')
    op.drop_index('ix_ai_call_logs_provider_id', table_name='ai_call_logs')
    op.drop_index('ix_ai_call_logs_user_id', table_name='ai_call_logs')
    op.drop_index('ix_ai_call_logs_tenant_id', table_name='ai_call_logs')
    op.drop_index('ix_ai_call_logs_id', table_name='ai_call_logs')
    op.drop_table('ai_call_logs')
    
    op.drop_index('ix_ai_api_keys_is_active', table_name='ai_api_keys')
    op.drop_index('ix_ai_api_keys_tenant_id', table_name='ai_api_keys')
    op.drop_index('ix_ai_api_keys_provider_id', table_name='ai_api_keys')
    op.drop_index('ix_ai_api_keys_id', table_name='ai_api_keys')
    op.drop_table('ai_api_keys')
    
    op.drop_index('ix_ai_models_is_active', table_name='ai_models')
    op.drop_index('ix_ai_models_provider_id', table_name='ai_models')
    op.drop_index('ix_ai_models_name', table_name='ai_models')
    op.drop_index('ix_ai_models_code', table_name='ai_models')
    op.drop_index('ix_ai_models_id', table_name='ai_models')
    op.drop_table('ai_models')
    
    op.drop_index('ix_ai_providers_is_active', table_name='ai_providers')
    op.drop_index('ix_ai_providers_name', table_name='ai_providers')
    op.drop_index('ix_ai_providers_code', table_name='ai_providers')
    op.drop_index('ix_ai_providers_id', table_name='ai_providers')
    op.drop_table('ai_providers')
