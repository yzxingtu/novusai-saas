"""
租户角色相关 Schema

定义租户角色管理的请求和响应数据结构，支持多级角色层级结构
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.core.base_schema import BaseSchema
from app.enums.role import RoleType


class TenantAdminRoleResponse(BaseSchema):
    """租户角色响应"""
    
    id: int = Field(..., description="角色 ID")
    tenant_id: int = Field(..., description="租户 ID")
    code: str = Field(..., description="角色代码")
    name: str = Field(..., description="角色名称")
    description: str | None = Field(None, description="角色描述")
    is_system: bool = Field(..., description="是否系统内置")
    is_active: bool = Field(..., description="是否启用")
    sort_order: int = Field(0, description="排序")
    # 层级结构字段
    parent_id: int | None = Field(None, description="父角色 ID")
    path: str | None = Field(None, description="层级路径，如 /1/3/7/")
    level: int = Field(1, description="层级深度，根节点为 1")
    children_count: int = Field(0, description="子角色数量")
    has_children: bool = Field(False, description="是否有子角色")
    permissions_count: int = Field(0, description="权限数量")
    # 组织架构字段
    type: str = Field(RoleType.ROLE.value, description="节点类型: department/position/role")
    allow_members: bool = Field(True, description="是否允许添加成员")
    leader_id: int | None = Field(None, description="负责人 ID")
    leader_name: str | None = Field(None, description="负责人名称")
    member_count: int = Field(0, description="成员数量")
    created_at: datetime = Field(..., description="创建时间")


class TenantAdminRoleDetailResponse(TenantAdminRoleResponse):
    """租户角色详情响应（含权限）"""
    
    permission_ids: list[int] = Field(default_factory=list, description="权限 ID 列表")
    permission_codes: list[str] = Field(default_factory=list, description="权限代码列表")


class TenantAdminRoleTreeNode(TenantAdminRoleResponse):
    """租户角色树节点（含子节点）"""
    
    children: list[TenantAdminRoleTreeNode] = Field(default_factory=list, description="子角色列表")


class TenantAdminRoleCreateRequest(BaseSchema):
    """创建租户角色请求"""
    
    name: str = Field(..., min_length=1, max_length=50, description="角色名称")
    description: str | None = Field(None, max_length=500, description="角色描述")
    is_active: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, description="排序")
    parent_id: int | None = Field(None, description="父角色 ID，None 表示顶级角色")
    permission_ids: list[int] = Field(default_factory=list, description="权限 ID 列表")
    # 组织架构字段
    type: str = Field(RoleType.ROLE.value, description="节点类型: department/position/role")
    allow_members: bool = Field(True, description="是否允许添加成员")


class TenantAdminRoleUpdateRequest(BaseSchema):
    """更新租户角色请求"""
    
    name: str | None = Field(None, min_length=1, max_length=50, description="角色名称")
    description: str | None = Field(None, max_length=500, description="角色描述")
    is_active: bool | None = Field(None, description="是否启用")
    sort_order: int | None = Field(None, description="排序")
    parent_id: int | None = Field(None, description="父角色 ID")
    permission_ids: list[int] | None = Field(None, description="权限 ID 列表")
    # 组织架构字段
    type: str | None = Field(None, description="节点类型: department/position/role")
    allow_members: bool | None = Field(None, description="是否允许添加成员")
    leader_id: int | None = Field(None, description="负责人 ID")


class TenantAdminRolePermissionsRequest(BaseSchema):
    """分配租户角色权限请求"""
    
    permission_ids: list[int] = Field(..., description="权限 ID 列表")


class TenantAdminRoleMoveRequest(BaseSchema):
    """移动租户角色节点请求"""
    
    new_parent_id: int | None = Field(None, description="新父角色 ID，None 表示移动到根级")


# ========== 组织架构管理 Schema ==========

class TenantAdminRoleSetLeaderRequest(BaseSchema):
    """设置节点负责人请求"""
    
    leader_id: int | None = Field(None, description="负责人 ID，None 表示取消负责人")


class TenantAdminRoleAddMemberRequest(BaseSchema):
    """添加成员到节点请求"""
    
    admin_id: int = Field(..., description="租户管理员 ID")


class TenantAdminRoleMemberResponse(BaseSchema):
    """节点成员响应"""
    
    id: int = Field(..., description="租户管理员 ID")
    username: str = Field(..., description="用户名")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像")
    email: str = Field(..., description="邮箱")
    is_active: bool = Field(True, description="是否启用")
    is_leader: bool = Field(False, description="是否是负责人")
    role_id: int | None = Field(None, description="角色/节点 ID")
    role_name: str | None = Field(None, description="角色/节点名称")
    created_at: datetime | None = Field(None, description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")


__all__ = [
    "TenantAdminRoleResponse",
    "TenantAdminRoleDetailResponse",
    "TenantAdminRoleTreeNode",
    "TenantAdminRoleCreateRequest",
    "TenantAdminRoleUpdateRequest",
    "TenantAdminRolePermissionsRequest",
    "TenantAdminRoleMoveRequest",
    # 组织架构管理
    "TenantAdminRoleSetLeaderRequest",
    "TenantAdminRoleAddMemberRequest",
    "TenantAdminRoleMemberResponse",
]
