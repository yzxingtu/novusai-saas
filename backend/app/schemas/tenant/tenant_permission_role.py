"""
Tenant admin permission role schemas / 企业管理员权限角色 Schema
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.base_schema import BaseSchema


class TenantPermissionRoleResponse(BaseSchema):
    """Tenant admin permission role response / 企业管理员权限角色响应"""

    id: int = Field(..., description="Permission role ID")
    tenant_id: int = Field(..., description="Tenant ID")
    code: str = Field(..., description="Permission role code")
    name: str = Field(..., description="Permission role name")
    description: str | None = Field(None, description="Permission role description")
    is_system: bool = Field(..., description="Whether the role is system built-in")
    is_active: bool = Field(..., description="Whether the role is active")
    sort_order: int = Field(0, description="Sort order")
    permissions_count: int = Field(0, description="Direct permission count")
    member_count: int = Field(0, description="Assigned admin count")
    created_at: datetime | None = Field(None, description="Created at")
    updated_at: datetime | None = Field(None, description="Updated at")


class TenantPermissionRoleDetailResponse(TenantPermissionRoleResponse):
    """Tenant admin permission role detail response / 企业管理员权限角色详情响应"""

    permission_ids: list[int] = Field(default_factory=list, description="Permission ID list")
    permission_codes: list[str] = Field(default_factory=list, description="Permission code list")


class TenantPermissionRoleCreateRequest(BaseSchema):
    """Create tenant admin permission role request / 创建企业管理员权限角色请求"""

    name: str = Field(..., min_length=1, max_length=50, description="Permission role name")
    code: str | None = Field(None, min_length=1, max_length=50, description="Permission role code")
    description: str | None = Field(None, max_length=500, description="Permission role description")
    is_active: bool = Field(True, description="Whether the role is active")
    sort_order: int = Field(0, description="Sort order")
    permission_ids: list[int] = Field(default_factory=list, description="Permission ID list")


class TenantPermissionRoleUpdateRequest(BaseSchema):
    """Update tenant admin permission role request / 更新企业管理员权限角色请求"""

    name: str | None = Field(None, min_length=1, max_length=50, description="Permission role name")
    code: str | None = Field(None, min_length=1, max_length=50, description="Permission role code")
    description: str | None = Field(None, max_length=500, description="Permission role description")
    is_active: bool | None = Field(None, description="Whether the role is active")
    sort_order: int | None = Field(None, description="Sort order")
    permission_ids: list[int] | None = Field(None, description="Permission ID list")


class TenantPermissionRolePermissionsRequest(BaseSchema):
    """Assign permissions request / 分配权限请求"""

    permission_ids: list[int] = Field(..., description="Permission ID list")


__all__ = [
    "TenantPermissionRoleCreateRequest",
    "TenantPermissionRoleDetailResponse",
    "TenantPermissionRolePermissionsRequest",
    "TenantPermissionRoleResponse",
    "TenantPermissionRoleUpdateRequest",
]
