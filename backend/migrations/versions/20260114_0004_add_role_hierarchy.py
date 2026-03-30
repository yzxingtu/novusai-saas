# -*- coding: utf-8 -*-
"""add role hierarchy support

为 admin_roles 和 tenant_admin_roles 表添加多级角色支持字段

Revision ID: 20260114_0004
Revises: 20260113_0003
Create Date: 2026-01-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260114_0004'
down_revision: Union[str, None] = '20260113_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加多级角色支持字段"""
    # admin_roles 表添加字段
    op.add_column('admin_roles', sa.Column(
        'parent_id', 
        sa.Integer(), 
        sa.ForeignKey('admin_roles.id', ondelete='SET NULL'),
        nullable=True,
        comment='父角色 ID'
    ))
    op.add_column('admin_roles', sa.Column(
        'path', 
        sa.String(500), 
        nullable=True,
        comment='层级路径，如 /1/3/7/'
    ))
    op.add_column('admin_roles', sa.Column(
        'level', 
        sa.Integer(), 
        nullable=False,
        server_default='1',
        comment='层级深度，根节点为 1'
    ))
    
    # 为 admin_roles.parent_id 添加索引
    op.create_index('ix_admin_roles_parent_id', 'admin_roles', ['parent_id'])
    # 为 admin_roles.path 添加索引（用于查询祖先/后代）
    op.create_index('ix_admin_roles_path', 'admin_roles', ['path'])
    
    # tenant_admin_roles 表添加字段
    op.add_column('tenant_admin_roles', sa.Column(
        'parent_id', 
        sa.Integer(), 
        sa.ForeignKey('tenant_admin_roles.id', ondelete='SET NULL'),
        nullable=True,
        comment='父角色 ID'
    ))
    op.add_column('tenant_admin_roles', sa.Column(
        'path', 
        sa.String(500), 
        nullable=True,
        comment='层级路径，如 /1/3/7/'
    ))
    op.add_column('tenant_admin_roles', sa.Column(
        'level', 
        sa.Integer(), 
        nullable=False,
        server_default='1',
        comment='层级深度，根节点为 1'
    ))
    
    # 为 tenant_admin_roles.parent_id 添加索引
    op.create_index('ix_tenant_admin_roles_parent_id', 'tenant_admin_roles', ['parent_id'])
    # 为 tenant_admin_roles.path 添加索引
    op.create_index('ix_tenant_admin_roles_path', 'tenant_admin_roles', ['path'])
    
    # 初始化现有角色数据：设置 path 为 /{id}/，level 为 1
    # 使用原生 SQL 更新现有数据
    op.execute(sa.text("""
        UPDATE admin_roles 
        SET path = '/' || id || '/', level = 1 
        WHERE path IS NULL
    """))
    op.execute(sa.text("""
        UPDATE tenant_admin_roles 
        SET path = '/' || id || '/', level = 1 
        WHERE path IS NULL
    """))


def downgrade() -> None:
    """移除多级角色支持字段"""
    # 移除 tenant_admin_roles 的索引和字段
    op.drop_index('ix_tenant_admin_roles_path', 'tenant_admin_roles')
    op.drop_index('ix_tenant_admin_roles_parent_id', 'tenant_admin_roles')
    op.drop_column('tenant_admin_roles', 'level')
    op.drop_column('tenant_admin_roles', 'path')
    op.drop_column('tenant_admin_roles', 'parent_id')
    
    # 移除 admin_roles 的索引和字段
    op.drop_index('ix_admin_roles_path', 'admin_roles')
    op.drop_index('ix_admin_roles_parent_id', 'admin_roles')
    op.drop_column('admin_roles', 'level')
    op.drop_column('admin_roles', 'path')
    op.drop_column('admin_roles', 'parent_id')
