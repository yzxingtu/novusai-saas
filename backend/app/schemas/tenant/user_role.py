"""
租户用户角色相关 Schema / Tenant User Role Schema

定义租户用户角色管理的请求和响应数据结构（扁平结构，无层级）
Defines tenant user role management request/response data structures (flat structure, no hierarchy).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.base_schema import BaseSchema


class TenantUserRoleResponse(BaseSchema):
    """租户用户角色响应"""

    id: int = Field(..., description="角色 ID")
    tenant_id: int = Field(..., description="租户 ID")
    name: str = Field(..., description="角色名称")
    code: str = Field(..., description="角色代码")
    description: str | None = Field(None, description="角色描述")
    is_system: bool = Field(False, description="是否系统内置")
    is_active: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, description="排序")
    permissions_count: int = Field(0, description="权限数量")
    member_count: int = Field(0, description="成员数量")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")


class TenantUserRoleDetailResponse(TenantUserRoleResponse):
    """租户用户角色详情响应（含权限）"""

    permission_ids: list[int] = Field(default_factory=list, description="权限 ID 列表")
    permission_codes: list[str] = Field(default_factory=list, description="权限代码列表")


class TenantUserRoleCreateRequest(BaseSchema):
    """创建租户用户角色请求"""

    name: str = Field(..., min_length=1, max_length=50, description="角色名称")
    code: str | None = Field(None, min_length=1, max_length=50, description="角色代码（为空时自动生成）")
    description: str | None = Field(None, max_length=500, description="角色描述")
    is_active: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, description="排序")
    permission_ids: list[int] = Field(default_factory=list, description="权限 ID 列表")


class TenantUserRoleUpdateRequest(BaseSchema):
    """更新租户用户角色请求"""

    name: str | None = Field(None, min_length=1, max_length=50, description="角色名称")
    code: str | None = Field(None, min_length=1, max_length=50, description="角色代码")
    description: str | None = Field(None, max_length=500, description="角色描述")
    is_active: bool | None = Field(None, description="是否启用")
    sort_order: int | None = Field(None, description="排序")
    permission_ids: list[int] | None = Field(None, description="权限 ID 列表")


class TenantUserRolePermissionsRequest(BaseSchema):
    """分配租户用户角色权限请求"""

    permission_ids: list[int] = Field(..., description="权限 ID 列表")


__all__ = [
    "TenantUserRoleResponse",
    "TenantUserRoleDetailResponse",
    "TenantUserRoleCreateRequest",
    "TenantUserRoleUpdateRequest",
    "TenantUserRolePermissionsRequest",
]
