"""
Admin permission role schemas / 管理后台权限角色 Schema
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.base_schema import BaseSchema


class AdminPermissionRoleResponse(BaseSchema):
    """Admin permission role response / 管理后台权限角色响应"""

    id: int = Field(..., description="Permission role ID")
    code: str = Field(..., description="Permission role code")
    name: str = Field(..., description="Permission role name")
    description: str | None = Field(None, description="Permission role description")
    is_system: bool = Field(..., description="Whether the role is system built-in")
    is_active: bool = Field(..., description="Whether the role is active")
    sort_order: int = Field(0, description="Sort order")
    permissions_count: int = Field(0, description="Direct permission count")
    created_at: datetime = Field(..., description="Created at")


class AdminPermissionRoleDetailResponse(AdminPermissionRoleResponse):
    """Admin permission role detail response / 管理后台权限角色详情响应"""

    permission_ids: list[int] = Field(
        default_factory=list, description="Permission ID list"
    )
    permission_codes: list[str] = Field(
        default_factory=list, description="Permission code list"
    )


class AdminPermissionRoleCreateRequest(BaseSchema):
    """Create admin permission role request / 创建管理后台权限角色请求"""

    name: str = Field(
        ..., min_length=1, max_length=50, description="Permission role name"
    )
    code: str | None = Field(
        None, min_length=1, max_length=50, description="Permission role code"
    )
    description: str | None = Field(
        None, max_length=500, description="Permission role description"
    )
    is_active: bool = Field(True, description="Whether the role is active")
    sort_order: int = Field(0, description="Sort order")
    permission_ids: list[int] = Field(
        default_factory=list, description="Permission ID list"
    )


class AdminPermissionRoleUpdateRequest(BaseSchema):
    """Update admin permission role request / 更新管理后台权限角色请求"""

    name: str | None = Field(
        None, min_length=1, max_length=50, description="Permission role name"
    )
    code: str | None = Field(
        None, min_length=1, max_length=50, description="Permission role code"
    )
    description: str | None = Field(
        None, max_length=500, description="Permission role description"
    )
    is_active: bool | None = Field(None, description="Whether the role is active")
    sort_order: int | None = Field(None, description="Sort order")
    permission_ids: list[int] | None = Field(None, description="Permission ID list")


class AdminPermissionRoleAssignPermissionsRequest(BaseSchema):
    """Assign permissions to admin permission role / 分配权限到管理后台权限角色请求"""

    permission_ids: list[int] = Field(..., description="Permission ID list")


__all__ = [
    "AdminPermissionRoleAssignPermissionsRequest",
    "AdminPermissionRoleCreateRequest",
    "AdminPermissionRoleDetailResponse",
    "AdminPermissionRoleResponse",
    "AdminPermissionRoleUpdateRequest",
]
