"""
平台角色相关 Schema

定义平台角色管理的请求和响应数据结构，支持多级角色层级结构
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.core.base_schema import BaseSchema
from app.enums.role import RoleType


class AdminRoleResponse(BaseSchema):
    """平台角色响应"""
    
    id: int = Field(..., description="角色 ID")
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


class AdminRoleDetailResponse(AdminRoleResponse):
    """平台角色详情响应（含权限）"""
    
    permission_ids: list[int] = Field(default_factory=list, description="权限 ID 列表")
    permission_codes: list[str] = Field(default_factory=list, description="权限代码列表")


class AdminRoleTreeNode(AdminRoleResponse):
    """平台角色树节点（含子节点）"""
    
    children: list[AdminRoleTreeNode] = Field(default_factory=list, description="子角色列表")


class AdminRoleCreateRequest(BaseSchema):
    """创建平台角色请求"""
    
    name: str = Field(..., min_length=1, max_length=50, description="角色名称")
    description: str | None = Field(None, max_length=500, description="角色描述")
    is_active: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, description="排序")
    parent_id: int | None = Field(None, description="父角色 ID，None 表示顶级角色")
    permission_ids: list[int] = Field(default_factory=list, description="权限 ID 列表")
    # 组织架构字段
    type: str = Field(RoleType.ROLE.value, description="节点类型: department/position/role")
    allow_members: bool = Field(True, description="是否允许添加成员")


class AdminRoleUpdateRequest(BaseSchema):
    """更新平台角色请求"""
    
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


class AdminRolePermissionsRequest(BaseSchema):
    """分配角色权限请求"""
    
    permission_ids: list[int] = Field(..., description="权限 ID 列表")


class AdminRoleMoveRequest(BaseSchema):
    """移动角色节点请求"""
    
    new_parent_id: int | None = Field(None, description="新父角色 ID，None 表示移动到根级")


# ========== 组织架构管理 Schema ==========

class AdminRoleSetLeaderRequest(BaseSchema):
    """设置节点负责人请求"""
    
    leader_id: int | None = Field(None, description="负责人 ID，None 表示取消负责人")


class AdminRoleAddMemberRequest(BaseSchema):
    """添加成员到节点请求"""
    
    admin_id: int = Field(..., description="管理员 ID")


class AdminRoleMemberResponse(BaseSchema):
    """节点成员响应"""
    
    id: int = Field(..., description="管理员 ID")
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
    "AdminRoleResponse",
    "AdminRoleDetailResponse",
    "AdminRoleTreeNode",
    "AdminRoleCreateRequest",
    "AdminRoleUpdateRequest",
    "AdminRolePermissionsRequest",
    "AdminRoleMoveRequest",
    # 组织架构管理
    "AdminRoleSetLeaderRequest",
    "AdminRoleAddMemberRequest",
    "AdminRoleMemberResponse",
]
