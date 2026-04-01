"""add plugins and tenant_plugins tables

Revision ID: 20260213_plugins
Revises: 20260213_seed_rb
Create Date: 2026-02-13 05:36:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '20260213_plugins'
down_revision: Union[str, None] = '20260213_seed_rb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create plugins and tenant_plugins tables."""
    op.create_table(
        'plugins',
        sa.Column('name', sa.String(length=100), nullable=False, comment='插件唯一标识'),
        sa.Column('display_name', sa.String(length=200), nullable=False, comment='插件显示名称'),
        sa.Column('version', sa.String(length=50), nullable=False, comment='当前版本号（semver）'),
        sa.Column('description', sa.Text(), nullable=True, comment='插件描述'),
        sa.Column('author', sa.String(length=200), nullable=True, comment='作者'),
        sa.Column('plugin_type', sa.String(length=30), nullable=False, comment='插件类型'),
        sa.Column('status', sa.String(length=20), nullable=False, comment='插件状态'),
        sa.Column('entry_point', sa.String(length=255), nullable=False, comment='入口点'),
        sa.Column('manifest', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='manifest.json 内容'),
        sa.Column('is_system', sa.Boolean(), nullable=False, comment='是否为系统内置插件'),
        sa.Column('required_permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='所需权限声明列表'),
        sa.Column('dependencies', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='依赖声明'),
        sa.Column('conflicts', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='互斥插件列表'),
        sa.Column('platform_version', sa.String(length=50), nullable=True, comment='最低平台版本要求'),
        sa.Column('config_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='配置项 JSON Schema'),
        sa.Column('default_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='默认配置值'),
        sa.Column('version_history', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='版本历史记录'),
        sa.Column('icon', sa.String(length=200), nullable=True, comment='插件图标'),
        sa.Column('homepage', sa.String(length=500), nullable=True, comment='插件主页 URL'),
        sa.Column('readme', sa.Text(), nullable=True, comment='README 内容'),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, comment='软删除标记'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True, comment='删除时间'),
        sa.Column('delete_level', sa.String(length=20), nullable=True, comment='删除层级'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_plugins_name'),
    )
    op.create_index(op.f('ix_plugins_id'), 'plugins', ['id'], unique=False)
    op.create_index(op.f('ix_plugins_is_deleted'), 'plugins', ['is_deleted'], unique=False)
    op.create_index('ix_plugins_type_status', 'plugins', ['plugin_type', 'status'], unique=False)

    op.create_table(
        'tenant_plugins',
        sa.Column('tenant_id', sa.Integer(), nullable=False, comment='企业 ID'),
        sa.Column('plugin_id', sa.Integer(), nullable=False, comment='插件 ID'),
        sa.Column('is_active', sa.Boolean(), nullable=False, comment='是否启用'),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='企业自定义配置'),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, comment='软删除标记'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True, comment='删除时间'),
        sa.Column('delete_level', sa.String(length=20), nullable=True, comment='删除层级'),
        sa.ForeignKeyConstraint(['plugin_id'], ['plugins.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'plugin_id', name='uq_tenant_plugins_tenant_plugin'),
    )
    op.create_index(op.f('ix_tenant_plugins_id'), 'tenant_plugins', ['id'], unique=False)
    op.create_index(op.f('ix_tenant_plugins_is_deleted'), 'tenant_plugins', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_tenant_plugins_plugin_id'), 'tenant_plugins', ['plugin_id'], unique=False)
    op.create_index(op.f('ix_tenant_plugins_tenant_id'), 'tenant_plugins', ['tenant_id'], unique=False)


def downgrade() -> None:
    """Drop plugins and tenant_plugins tables."""
    op.drop_index(op.f('ix_tenant_plugins_tenant_id'), table_name='tenant_plugins')
    op.drop_index(op.f('ix_tenant_plugins_plugin_id'), table_name='tenant_plugins')
    op.drop_index(op.f('ix_tenant_plugins_is_deleted'), table_name='tenant_plugins')
    op.drop_index(op.f('ix_tenant_plugins_id'), table_name='tenant_plugins')
    op.drop_table('tenant_plugins')

    op.drop_index('ix_plugins_type_status', table_name='plugins')
    op.drop_index(op.f('ix_plugins_is_deleted'), table_name='plugins')
    op.drop_index(op.f('ix_plugins_id'), table_name='plugins')
    op.drop_table('plugins')
