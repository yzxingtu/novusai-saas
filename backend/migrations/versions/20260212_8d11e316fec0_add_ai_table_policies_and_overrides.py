"""add_ai_table_policies_and_overrides

Revision ID: 8d11e316fec0
Revises: 6f8e790c9a68
Create Date: 2026-02-12 17:21:42.621910+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8d11e316fec0'
down_revision: Union[str, None] = '6f8e790c9a68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # ai_table_policies - AI 表访问策略（平台级）
    op.create_table(
        'ai_table_policies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('table_name', sa.String(length=100), nullable=False, comment='表名'),
        sa.Column('label', sa.String(length=100), nullable=False, comment='显示名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='表描述'),
        sa.Column('keywords', sa.JSON(), nullable=True, comment='关键词/别名'),
        sa.Column('column_descriptions', sa.JSON(), nullable=True, comment='列描述'),
        sa.Column('allow_read', sa.Boolean(), nullable=False, comment='允许查询'),
        sa.Column('allow_create', sa.Boolean(), nullable=False, comment='允许创建'),
        sa.Column('allow_update', sa.Boolean(), nullable=False, comment='允许更新'),
        sa.Column('allow_delete', sa.Boolean(), nullable=False, comment='允许删除'),
        sa.Column('max_rows', sa.Integer(), nullable=False, comment='单次查询最大行数'),
        sa.Column('blocked_columns', sa.JSON(), nullable=True, comment='屏蔽列'),
        sa.Column('readonly_columns', sa.JSON(), nullable=True, comment='只读列'),
        sa.Column('scope', sa.String(length=20), nullable=False, comment='作用域'),
        sa.Column('permission_code', sa.String(length=100), nullable=False, comment='权限码'),
        sa.Column('sort_order', sa.Integer(), nullable=False, comment='排序'),
        sa.Column('is_active', sa.Boolean(), nullable=False, comment='启用状态'),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, comment='软删除标记'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'idx_ai_table_policies_scope_active',
        'ai_table_policies', ['scope', 'is_active'],
    )
    op.create_index(
        op.f('ix_ai_table_policies_id'),
        'ai_table_policies', ['id'],
    )
    op.create_index(
        op.f('ix_ai_table_policies_is_active'),
        'ai_table_policies', ['is_active'],
    )
    op.create_index(
        op.f('ix_ai_table_policies_is_deleted'),
        'ai_table_policies', ['is_deleted'],
    )
    op.create_index(
        op.f('ix_ai_table_policies_scope'),
        'ai_table_policies', ['scope'],
    )
    op.create_index(
        op.f('ix_ai_table_policies_table_name'),
        'ai_table_policies', ['table_name'], unique=True,
    )

    # ai_table_policy_overrides - AI 表策略租户级覆盖
    op.create_table(
        'ai_table_policy_overrides',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('policy_id', sa.Integer(), nullable=False, comment='策略 ID'),
        sa.Column('allow_read', sa.Boolean(), nullable=True, comment='覆盖查询权限'),
        sa.Column('allow_create', sa.Boolean(), nullable=True, comment='覆盖创建权限'),
        sa.Column('allow_update', sa.Boolean(), nullable=True, comment='覆盖更新权限'),
        sa.Column('allow_delete', sa.Boolean(), nullable=True, comment='覆盖删除权限'),
        sa.Column('max_rows', sa.Integer(), nullable=True, comment='覆盖最大行数'),
        sa.Column('blocked_columns', sa.JSON(), nullable=True, comment='追加屏蔽列'),
        sa.Column('is_active', sa.Boolean(), nullable=True, comment='覆盖启用状态'),
        sa.Column('tenant_id', sa.Integer(), nullable=False, comment='租户ID'),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, comment='软删除标记'),
        sa.ForeignKeyConstraint(['policy_id'], ['ai_table_policies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_ai_table_policy_overrides_id'),
        'ai_table_policy_overrides', ['id'],
    )
    op.create_index(
        op.f('ix_ai_table_policy_overrides_is_deleted'),
        'ai_table_policy_overrides', ['is_deleted'],
    )
    op.create_index(
        op.f('ix_ai_table_policy_overrides_policy_id'),
        'ai_table_policy_overrides', ['policy_id'],
    )
    op.create_index(
        op.f('ix_ai_table_policy_overrides_tenant_id'),
        'ai_table_policy_overrides', ['tenant_id'],
    )
    op.create_index(
        'uq_policy_override_tenant_policy',
        'ai_table_policy_overrides', ['tenant_id', 'policy_id'],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index('uq_policy_override_tenant_policy', table_name='ai_table_policy_overrides')
    op.drop_index(op.f('ix_ai_table_policy_overrides_tenant_id'), table_name='ai_table_policy_overrides')
    op.drop_index(op.f('ix_ai_table_policy_overrides_policy_id'), table_name='ai_table_policy_overrides')
    op.drop_index(op.f('ix_ai_table_policy_overrides_is_deleted'), table_name='ai_table_policy_overrides')
    op.drop_index(op.f('ix_ai_table_policy_overrides_id'), table_name='ai_table_policy_overrides')
    op.drop_table('ai_table_policy_overrides')

    op.drop_index(op.f('ix_ai_table_policies_table_name'), table_name='ai_table_policies')
    op.drop_index(op.f('ix_ai_table_policies_scope'), table_name='ai_table_policies')
    op.drop_index(op.f('ix_ai_table_policies_is_deleted'), table_name='ai_table_policies')
    op.drop_index(op.f('ix_ai_table_policies_is_active'), table_name='ai_table_policies')
    op.drop_index(op.f('ix_ai_table_policies_id'), table_name='ai_table_policies')
    op.drop_index('idx_ai_table_policies_scope_active', table_name='ai_table_policies')
    op.drop_table('ai_table_policies')
