# -*- coding: utf-8 -*-
"""Initial migration - Create all tables and seed initial admin user

Revision ID: 0001
Revises: 
Create Date: 2026-01-11

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# 密码哈希生成
import bcrypt


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables and seed initial data."""
    
    # ========================================
    # 1. 创建权限表 (permissions)
    # ========================================
    op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False, comment='权限代码'),
        sa.Column('name', sa.String(length=100), nullable=False, comment='权限名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='权限描述'),
        sa.Column('type', sa.String(length=20), nullable=False, comment='权限类型: menu/operation'),
        sa.Column('scope', sa.String(length=20), nullable=False, comment='作用域: admin/tenant/both'),
        sa.Column('resource', sa.String(length=50), nullable=False, comment='资源标识'),
        sa.Column('action', sa.String(length=50), nullable=False, comment='操作标识'),
        sa.Column('parent_id', sa.Integer(), nullable=True, comment='父级权限 ID'),
        sa.Column('sort_order', sa.Integer(), nullable=False, default=0, comment='排序'),
        sa.Column('icon', sa.String(length=50), nullable=True, comment='图标'),
        sa.Column('path', sa.String(length=200), nullable=True, comment='前端路由'),
        sa.Column('component', sa.String(length=200), nullable=True, comment='前端组件'),
        sa.Column('hidden', sa.Boolean(), nullable=False, default=False, comment='是否隐藏菜单'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=True, comment='是否启用'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_id'], ['permissions.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_permissions_id', 'permissions', ['id'])
    op.create_index('ix_permissions_code', 'permissions', ['code'])
    op.create_index('ix_permissions_type', 'permissions', ['type'])
    op.create_index('ix_permissions_scope', 'permissions', ['scope'])
    op.create_index('ix_permissions_resource', 'permissions', ['resource'])
    op.create_index('ix_permissions_is_enabled', 'permissions', ['is_enabled'])
    op.create_index('ix_permissions_is_deleted', 'permissions', ['is_deleted'])
    
    # ========================================
    # 2. 创建平台管理员角色表 (admin_roles)
    # ========================================
    op.create_table(
        'admin_roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False, comment='角色名称'),
        sa.Column('code', sa.String(length=50), nullable=False, comment='角色代码'),
        sa.Column('description', sa.Text(), nullable=True, comment='角色描述'),
        sa.Column('is_system', sa.Boolean(), nullable=False, default=False, comment='是否系统内置'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='是否启用'),
        sa.Column('sort_order', sa.Integer(), nullable=False, default=0, comment='排序'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_admin_roles_id', 'admin_roles', ['id'])
    op.create_index('ix_admin_roles_code', 'admin_roles', ['code'])
    op.create_index('ix_admin_roles_is_deleted', 'admin_roles', ['is_deleted'])
    
    # ========================================
    # 3. 创建平台角色-权限关联表
    # ========================================
    op.create_table(
        'admin_role_permissions',
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['admin_roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'permission_id'),
    )
    
    # ========================================
    # 4. 创建平台管理员表 (admins)
    # ========================================
    op.create_table(
        'admins',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False, comment='用户名'),
        sa.Column('email', sa.String(length=255), nullable=False, comment='邮箱'),
        sa.Column('phone', sa.String(length=20), nullable=True, comment='手机号'),
        sa.Column('password_hash', sa.String(length=255), nullable=False, comment='密码哈希'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='是否激活'),
        sa.Column('is_super', sa.Boolean(), nullable=False, default=False, comment='是否超级管理员'),
        sa.Column('nickname', sa.String(length=100), nullable=True, comment='昵称'),
        sa.Column('avatar', sa.String(length=500), nullable=True, comment='头像 URL'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True, comment='最后登录时间'),
        sa.Column('last_login_ip', sa.String(length=50), nullable=True, comment='最后登录 IP'),
        sa.Column('role_id', sa.Integer(), nullable=True, comment='角色 ID'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['role_id'], ['admin_roles.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('phone'),
    )
    op.create_index('ix_admins_id', 'admins', ['id'])
    op.create_index('ix_admins_username', 'admins', ['username'])
    op.create_index('ix_admins_email', 'admins', ['email'])
    op.create_index('ix_admins_phone', 'admins', ['phone'])
    op.create_index('ix_admins_is_deleted', 'admins', ['is_deleted'])
    
    # ========================================
    # 5. 创建企业表 (tenants)
    # ========================================
    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False, comment='企业名称'),
        sa.Column('code', sa.String(length=50), nullable=False, comment='企业编码'),
        sa.Column('contact_name', sa.String(length=50), nullable=True, comment='联系人姓名'),
        sa.Column('contact_phone', sa.String(length=20), nullable=True, comment='联系人电话'),
        sa.Column('contact_email', sa.String(length=255), nullable=True, comment='联系人邮箱'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='是否启用'),
        sa.Column('plan', sa.String(length=50), nullable=False, default='free', comment='套餐类型'),
        sa.Column('quota', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='配额配置'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, comment='到期时间'),
        sa.Column('remark', sa.Text(), nullable=True, comment='备注'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_tenants_id', 'tenants', ['id'])
    op.create_index('ix_tenants_name', 'tenants', ['name'])
    op.create_index('ix_tenants_code', 'tenants', ['code'])
    op.create_index('ix_tenants_is_deleted', 'tenants', ['is_deleted'])
    
    # ========================================
    # 6. 创建企业管理员角色表 (tenant_admin_roles)
    # ========================================
    op.create_table(
        'tenant_admin_roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False, comment='企业 ID'),
        sa.Column('name', sa.String(length=50), nullable=False, comment='角色名称'),
        sa.Column('code', sa.String(length=50), nullable=False, comment='角色代码'),
        sa.Column('description', sa.Text(), nullable=True, comment='角色描述'),
        sa.Column('is_system', sa.Boolean(), nullable=False, default=False, comment='是否系统内置'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='是否启用'),
        sa.Column('sort_order', sa.Integer(), nullable=False, default=0, comment='排序'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tenant_admin_roles_id', 'tenant_admin_roles', ['id'])
    op.create_index('ix_tenant_admin_roles_tenant_id', 'tenant_admin_roles', ['tenant_id'])
    op.create_index('ix_tenant_admin_roles_code', 'tenant_admin_roles', ['code'])
    op.create_index('ix_tenant_admin_roles_is_deleted', 'tenant_admin_roles', ['is_deleted'])
    
    # ========================================
    # 7. 创建企业角色-权限关联表
    # ========================================
    op.create_table(
        'tenant_admin_role_permissions',
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['tenant_admin_roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'permission_id'),
    )
    
    # ========================================
    # 8. 创建企业管理员表 (tenant_admins)
    # ========================================
    op.create_table(
        'tenant_admins',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False, comment='企业 ID'),
        sa.Column('username', sa.String(length=50), nullable=False, comment='用户名'),
        sa.Column('email', sa.String(length=255), nullable=False, comment='邮箱'),
        sa.Column('phone', sa.String(length=20), nullable=True, comment='手机号'),
        sa.Column('password_hash', sa.String(length=255), nullable=False, comment='密码哈希'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='是否激活'),
        sa.Column('is_owner', sa.Boolean(), nullable=False, default=False, comment='是否企业所有者'),
        sa.Column('nickname', sa.String(length=100), nullable=True, comment='昵称'),
        sa.Column('avatar', sa.String(length=500), nullable=True, comment='头像 URL'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True, comment='最后登录时间'),
        sa.Column('last_login_ip', sa.String(length=50), nullable=True, comment='最后登录 IP'),
        sa.Column('role_id', sa.Integer(), nullable=True, comment='角色 ID'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['role_id'], ['tenant_admin_roles.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_tenant_admins_id', 'tenant_admins', ['id'])
    op.create_index('ix_tenant_admins_tenant_id', 'tenant_admins', ['tenant_id'])
    op.create_index('ix_tenant_admins_username', 'tenant_admins', ['username'])
    op.create_index('ix_tenant_admins_email', 'tenant_admins', ['email'])
    op.create_index('ix_tenant_admins_phone', 'tenant_admins', ['phone'])
    op.create_index('ix_tenant_admins_is_deleted', 'tenant_admins', ['is_deleted'])
    
    # ========================================
    # 9. 创建企业业务用户表 (tenant_users)
    # ========================================
    op.create_table(
        'tenant_users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False, comment='企业 ID'),
        sa.Column('username', sa.String(length=50), nullable=True, comment='用户名'),
        sa.Column('email', sa.String(length=255), nullable=True, comment='邮箱'),
        sa.Column('phone', sa.String(length=20), nullable=True, comment='手机号'),
        sa.Column('password_hash', sa.String(length=255), nullable=True, comment='密码哈希'),
        sa.Column('openid', sa.String(length=100), nullable=True, comment='微信 OpenID'),
        sa.Column('unionid', sa.String(length=100), nullable=True, comment='微信 UnionID'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='是否激活'),
        sa.Column('nickname', sa.String(length=100), nullable=True, comment='昵称'),
        sa.Column('avatar', sa.String(length=500), nullable=True, comment='头像 URL'),
        sa.Column('gender', sa.Integer(), nullable=False, default=0, comment='性别: 0未知 1男 2女'),
        sa.Column('extra', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='扩展信息'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True, comment='最后登录时间'),
        sa.Column('last_login_ip', sa.String(length=50), nullable=True, comment='最后登录 IP'),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tenant_users_id', 'tenant_users', ['id'])
    op.create_index('ix_tenant_users_tenant_id', 'tenant_users', ['tenant_id'])
    op.create_index('ix_tenant_users_username', 'tenant_users', ['username'])
    op.create_index('ix_tenant_users_email', 'tenant_users', ['email'])
    op.create_index('ix_tenant_users_phone', 'tenant_users', ['phone'])
    op.create_index('ix_tenant_users_openid', 'tenant_users', ['openid'])
    op.create_index('ix_tenant_users_unionid', 'tenant_users', ['unionid'])
    op.create_index('ix_tenant_users_is_deleted', 'tenant_users', ['is_deleted'])
    
    # ========================================
    # 10. 插入初始数据
    # ========================================
    
    # 创建超级管理员账号
    # 用户名: admin
    # 密码: admin123456
    password = "admin123456"
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    now = datetime.utcnow()
    
    op.execute(
        sa.text(
            """
            INSERT INTO admins (username, email, password_hash, is_active, is_super, nickname, created_at, updated_at, is_deleted)
            VALUES (:username, :email, :password_hash, :is_active, :is_super, :nickname, :created_at, :updated_at, :is_deleted)
            """
        ).bindparams(
            username="admin",
            email="admin@novusai.local",
            password_hash=password_hash,
            is_active=True,
            is_super=True,
            nickname="超级管理员",
            created_at=now,
            updated_at=now,
            is_deleted=False,
        )
    )


def downgrade() -> None:
    """Drop all tables."""
    # 按照依赖关系的反序删除表
    
    # 删除企业业务用户表
    op.drop_index('ix_tenant_users_is_deleted', 'tenant_users')
    op.drop_index('ix_tenant_users_unionid', 'tenant_users')
    op.drop_index('ix_tenant_users_openid', 'tenant_users')
    op.drop_index('ix_tenant_users_phone', 'tenant_users')
    op.drop_index('ix_tenant_users_email', 'tenant_users')
    op.drop_index('ix_tenant_users_username', 'tenant_users')
    op.drop_index('ix_tenant_users_tenant_id', 'tenant_users')
    op.drop_index('ix_tenant_users_id', 'tenant_users')
    op.drop_table('tenant_users')
    
    # 删除企业管理员表
    op.drop_index('ix_tenant_admins_is_deleted', 'tenant_admins')
    op.drop_index('ix_tenant_admins_phone', 'tenant_admins')
    op.drop_index('ix_tenant_admins_email', 'tenant_admins')
    op.drop_index('ix_tenant_admins_username', 'tenant_admins')
    op.drop_index('ix_tenant_admins_tenant_id', 'tenant_admins')
    op.drop_index('ix_tenant_admins_id', 'tenant_admins')
    op.drop_table('tenant_admins')
    
    # 删除企业角色-权限关联表
    op.drop_table('tenant_admin_role_permissions')
    
    # 删除企业管理员角色表
    op.drop_index('ix_tenant_admin_roles_is_deleted', 'tenant_admin_roles')
    op.drop_index('ix_tenant_admin_roles_code', 'tenant_admin_roles')
    op.drop_index('ix_tenant_admin_roles_tenant_id', 'tenant_admin_roles')
    op.drop_index('ix_tenant_admin_roles_id', 'tenant_admin_roles')
    op.drop_table('tenant_admin_roles')
    
    # 删除企业表
    op.drop_index('ix_tenants_is_deleted', 'tenants')
    op.drop_index('ix_tenants_code', 'tenants')
    op.drop_index('ix_tenants_name', 'tenants')
    op.drop_index('ix_tenants_id', 'tenants')
    op.drop_table('tenants')
    
    # 删除平台管理员表
    op.drop_index('ix_admins_is_deleted', 'admins')
    op.drop_index('ix_admins_phone', 'admins')
    op.drop_index('ix_admins_email', 'admins')
    op.drop_index('ix_admins_username', 'admins')
    op.drop_index('ix_admins_id', 'admins')
    op.drop_table('admins')
    
    # 删除平台角色-权限关联表
    op.drop_table('admin_role_permissions')
    
    # 删除平台管理员角色表
    op.drop_index('ix_admin_roles_is_deleted', 'admin_roles')
    op.drop_index('ix_admin_roles_code', 'admin_roles')
    op.drop_index('ix_admin_roles_id', 'admin_roles')
    op.drop_table('admin_roles')
    
    # 删除权限表
    op.drop_index('ix_permissions_is_deleted', 'permissions')
    op.drop_index('ix_permissions_is_enabled', 'permissions')
    op.drop_index('ix_permissions_resource', 'permissions')
    op.drop_index('ix_permissions_scope', 'permissions')
    op.drop_index('ix_permissions_type', 'permissions')
    op.drop_index('ix_permissions_code', 'permissions')
    op.drop_index('ix_permissions_id', 'permissions')
    op.drop_table('permissions')
