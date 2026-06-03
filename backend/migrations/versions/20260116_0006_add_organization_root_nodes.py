# -*- coding: utf-8 -*-
"""add organization root nodes

为平台端和现有企业添加组织架构根节点

Revision ID: 0006_org_root
Revises: bd94c7f44d6c
Create Date: 2026-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '0006_org_root'
down_revision: Union[str, None] = 'bd94c7f44d6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    添加组织架构根节点
    
    1. 为平台端插入默认根节点
    2. 为现有企业补充根节点
    """
    conn = op.get_bind()
    
    # ========== 1. 平台端根节点 ==========
    # 检查是否已存在平台根节点
    result = conn.execute(text("""
        SELECT id FROM admin_roles 
        WHERE code = 'platform_root' AND is_deleted = false
    """))
    platform_root = result.fetchone()
    
    if not platform_root:
        # 插入平台端根节点
        conn.execute(text("""
            INSERT INTO admin_roles (
                name, code, description, is_system, is_active, sort_order,
                parent_id, level, type, allow_members,
                created_at, updated_at, is_deleted
            ) VALUES (
                '平台管理组', 'platform_root', '平台组织架构根节点，不可删除',
                true, true, 0,
                NULL, 1, 'department', true,
                NOW(), NOW(), false
            )
        """))
        
        # 获取刚插入的根节点 ID 并更新 path
        result = conn.execute(text("""
            SELECT id FROM admin_roles WHERE code = 'platform_root' AND is_deleted = false
        """))
        root_row = result.fetchone()
        if root_row:
            root_id = root_row[0]
            conn.execute(text("UPDATE admin_roles SET path = '/' || :rid || '/' WHERE id = :rid"), {"rid": root_id})
            
            # 将现有的顶级节点（parent_id IS NULL 且不是根节点）挂到根节点下
            conn.execute(text("""
                UPDATE admin_roles 
                SET parent_id = :rid,
                    level = level + 1,
                    path = '/' || :rid || '/' || COALESCE(path, '/' || id || '/')
                WHERE parent_id IS NULL 
                  AND id != :rid
                  AND is_deleted = false
            """), {"rid": root_id})
            
            # 将超级管理员关联到根节点，并设为负责人
            # 查找第一个超级管理员
            result = conn.execute(text("""
                SELECT id FROM admins 
                WHERE is_super = true AND is_deleted = false 
                ORDER BY id LIMIT 1
            """))
            super_admin = result.fetchone()
            if super_admin:
                super_admin_id = super_admin[0]
                # 将超级管理员关联到根节点
                conn.execute(text("UPDATE admins SET role_id = :rid WHERE id = :aid"), {"rid": root_id, "aid": super_admin_id})
                # 设置根节点负责人
                conn.execute(text("UPDATE admin_roles SET leader_id = :aid WHERE id = :rid"), {"aid": super_admin_id, "rid": root_id})
    
    # ========== 2. 企业端根节点 ==========
    # 查询所有企业
    result = conn.execute(text("""
        SELECT id, name FROM tenants WHERE is_deleted = false
    """))
    tenants = result.fetchall()
    
    for tenant in tenants:
        tenant_id = tenant[0]
        tenant_name = tenant[1]
        
        # 检查该企业是否已有根节点
        result = conn.execute(text("""
            SELECT id FROM tenant_admin_roles 
            WHERE tenant_id = :tid 
              AND code = 'tenant_root' 
              AND is_deleted = false
        """), {"tid": tenant_id})
        tenant_root = result.fetchone()
        
        if not tenant_root:
            # 插入企业根节点
            conn.execute(text("""
                INSERT INTO tenant_admin_roles (
                    tenant_id, name, code, description, is_system, is_active, sort_order,
                    parent_id, level, type, allow_members,
                    created_at, updated_at, is_deleted
                ) VALUES (
                    :tid, :tname, 'tenant_root', '企业组织架构根节点，不可删除',
                    true, true, 0,
                    NULL, 1, 'department', true,
                    NOW(), NOW(), false
                )
            """), {"tid": tenant_id, "tname": tenant_name})
            
            # 获取刚插入的根节点 ID 并更新 path
            result = conn.execute(text("""
                SELECT id FROM tenant_admin_roles 
                WHERE tenant_id = :tid AND code = 'tenant_root' AND is_deleted = false
            """), {"tid": tenant_id})
            root_row = result.fetchone()
            if root_row:
                root_id = root_row[0]
                conn.execute(text("UPDATE tenant_admin_roles SET path = '/' || :rid || '/' WHERE id = :rid"), {"rid": root_id})
                
                # 将现有的顶级节点挂到根节点下
                conn.execute(text("""
                    UPDATE tenant_admin_roles 
                    SET parent_id = :rid,
                        level = level + 1,
                        path = '/' || :rid || '/' || COALESCE(path, '/' || id || '/')
                    WHERE tenant_id = :tid
                      AND parent_id IS NULL 
                      AND id != :rid
                      AND is_deleted = false
                """), {"rid": root_id, "tid": tenant_id})
                
                # 将企业所有者关联到根节点并设为负责人
                result = conn.execute(text("""
                    SELECT id FROM tenant_admins 
                    WHERE tenant_id = :tid
                      AND is_owner = true
                      AND is_deleted = false
                    ORDER BY id LIMIT 1
                """), {"tid": tenant_id})
                owner = result.fetchone()
                if owner:
                    owner_id = owner[0]
                    # 将所有者关联到根节点
                    conn.execute(text("UPDATE tenant_admins SET role_id = :rid WHERE id = :oid"), {"rid": root_id, "oid": owner_id})
                    # 设置根节点负责人
                    conn.execute(text("UPDATE tenant_admin_roles SET leader_id = :oid WHERE id = :rid"), {"oid": owner_id, "rid": root_id})


def downgrade() -> None:
    """
    回滚：删除根节点（谨慎操作）
    
    注意：此操作可能导致数据不一致，建议不要在生产环境执行
    """
    conn = op.get_bind()
    
    # 获取平台根节点 ID
    result = conn.execute(text("""
        SELECT id FROM admin_roles WHERE code = 'platform_root' AND is_deleted = false
    """))
    platform_root = result.fetchone()
    
    if platform_root:
        root_id = platform_root[0]
        
        # 将子节点提升为顶级节点
        conn.execute(text("""
            UPDATE admin_roles 
            SET parent_id = NULL,
                level = level - 1
            WHERE parent_id = :rid AND is_deleted = false
        """), {"rid": root_id})
        
        # 删除根节点
        conn.execute(text("""
            UPDATE admin_roles SET is_deleted = true WHERE id = :rid
        """), {"rid": root_id})
    
    # 企业端根节点
    result = conn.execute(text("""
        SELECT id, tenant_id FROM tenant_admin_roles 
        WHERE code = 'tenant_root' AND is_deleted = false
    """))
    tenant_roots = result.fetchall()
    
    for root in tenant_roots:
        root_id = root[0]
        tenant_id = root[1]
        
        # 将子节点提升为顶级节点
        conn.execute(text("""
            UPDATE tenant_admin_roles 
            SET parent_id = NULL,
                level = level - 1
            WHERE parent_id = :rid AND is_deleted = false
        """), {"rid": root_id})
        
        # 清除所有者的角色关联（如果关联的是根节点）
        conn.execute(text("""
            UPDATE tenant_admins 
            SET role_id = NULL
            WHERE tenant_id = :tid
              AND role_id = :rid
              AND is_deleted = false
        """), {"tid": tenant_id, "rid": root_id})
        
        # 删除根节点
        conn.execute(text("""
            UPDATE tenant_admin_roles SET is_deleted = true WHERE id = :rid
        """), {"rid": root_id})
