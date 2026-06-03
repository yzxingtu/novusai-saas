# -*- coding: utf-8 -*-
"""Add tenant settings field and tenant_domains table

Revision ID: 0002
Revises: 0001
Create Date: 2026-01-12

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tenant settings and tenant_domains table."""
    
    # ========================================
    # 1. 给企业表添加 settings 字段
    # ========================================
    op.add_column(
        'tenants',
        sa.Column(
            'settings',
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            comment='企业设置'
        )
    )
    
    # ========================================
    # 2. 创建企业域名表 (tenant_domains)
    # ========================================
    op.create_table(
        'tenant_domains',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False, comment='企业 ID'),
        sa.Column('domain', sa.String(length=255), nullable=False, comment='域名'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False, comment='是否已验证'),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True, comment='验证时间'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, default=False, comment='是否主域名'),
        sa.Column('ssl_status', sa.String(length=20), nullable=False, default='pending', comment='SSL 状态'),
        sa.Column('ssl_expires_at', sa.DateTime(timezone=True), nullable=True, comment='SSL 证书到期时间'),
        sa.Column('verification_token', sa.String(length=100), nullable=True, comment='域名验证 Token'),
        sa.Column('remark', sa.Text(), nullable=True, comment='备注'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('domain'),
    )
    
    # 创建索引
    op.create_index('ix_tenant_domains_id', 'tenant_domains', ['id'])
    op.create_index('ix_tenant_domains_tenant_id', 'tenant_domains', ['tenant_id'])
    op.create_index('ix_tenant_domains_domain', 'tenant_domains', ['domain'])
    op.create_index('ix_tenant_domains_is_verified', 'tenant_domains', ['is_verified'])
    op.create_index('ix_tenant_domains_is_deleted', 'tenant_domains', ['is_deleted'])
    # 复合索引：企业ID + 是否主域名
    op.create_index('ix_tenant_domains_tenant_primary', 'tenant_domains', ['tenant_id', 'is_primary'])


def downgrade() -> None:
    """Remove tenant_domains table and settings field."""
    
    # 删除索引
    op.drop_index('ix_tenant_domains_tenant_primary', table_name='tenant_domains')
    op.drop_index('ix_tenant_domains_is_deleted', table_name='tenant_domains')
    op.drop_index('ix_tenant_domains_is_verified', table_name='tenant_domains')
    op.drop_index('ix_tenant_domains_domain', table_name='tenant_domains')
    op.drop_index('ix_tenant_domains_tenant_id', table_name='tenant_domains')
    op.drop_index('ix_tenant_domains_id', table_name='tenant_domains')
    
    # 删除表
    op.drop_table('tenant_domains')
    
    # 删除 settings 字段
    op.drop_column('tenants', 'settings')
