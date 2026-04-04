"""
Tenant organization node schemas / 企业组织节点 Schema
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.base_schema import BaseSchema
from app.enums.role import DataScope, RoleType

TenantOrgNodeType = Literal["department", "position"]


class TenantOrgNodeLeaderResponse(BaseSchema):
    """Tenant org node leader info / 企业组织节点负责人信息"""

    id: int = Field(..., description="Leader tenant admin ID")
    username: str = Field(..., description="Leader username")
    nickname: str | None = Field(None, description="Leader nickname")
    real_name: str | None = Field(None, description="Leader real name")
    avatar: str | None = Field(None, description="Leader avatar")


class TenantOrgNodeResponse(BaseSchema):
    """Tenant org node response / 企业组织节点响应"""

    id: int = Field(..., description="Organization node ID")
    tenant_id: int = Field(..., description="Tenant ID")
    code: str = Field(..., description="Organization node code")
    name: str = Field(..., description="Organization node name")
    description: str | None = Field(None, description="Organization node description")
    is_system: bool = Field(..., description="Whether the node is system built-in")
    is_active: bool = Field(..., description="Whether the node is active")
    sort_order: int = Field(0, description="Sort order")
    parent_id: int | None = Field(None, description="Parent organization node ID")
    path: str | None = Field(None, description="Materialized path")
    level: int = Field(1, description="Hierarchy level")
    children_count: int = Field(0, description="Direct child count")
    has_children: bool = Field(False, description="Whether the node has children")
    type: str = Field(RoleType.DEPARTMENT.value, description="Organization node type")
    allow_members: bool = Field(
        True, description="Whether members can be assigned to the node"
    )
    leader_id: int | None = Field(None, description="Leader tenant admin ID")
    leader: TenantOrgNodeLeaderResponse | None = Field(None, description="Leader info")
    leader_name: str | None = Field(None, description="Leader display name")
    member_count: int = Field(0, description="Direct member count")
    permissions_count: int = Field(0, description="Direct permission count")
    data_scope: str = Field(
        DataScope.DEPT_AND_CHILDREN.value,
        description="Organization authority scope policy",
    )
    custom_dept_ids: list[int] | None = Field(
        None,
        description="Custom organization node IDs used when data_scope=custom",
    )
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime | None = Field(None, description="Updated at")


class TenantOrgNodeDetailResponse(TenantOrgNodeResponse):
    """Tenant org node detail response / 企业组织节点详情响应"""

    permission_ids: list[int] = Field(
        default_factory=list, description="Assigned permission IDs"
    )
    permission_codes: list[str] = Field(
        default_factory=list, description="Assigned permission codes"
    )
    can_assign_permissions: bool = Field(
        False,
        description="Whether current tenant admin can assign permissions on the node",
    )


class TenantOrgNodeCreateRequest(BaseSchema):
    """Create tenant org node request / 创建企业组织节点请求"""

    name: str = Field(
        ..., min_length=1, max_length=50, description="Organization node name"
    )
    description: str | None = Field(
        None, max_length=500, description="Organization node description"
    )
    is_active: bool = Field(True, description="Whether the node is active")
    sort_order: int = Field(0, description="Sort order")
    parent_id: int | None = Field(None, description="Parent organization node ID")
    type: TenantOrgNodeType = Field(
        RoleType.DEPARTMENT.value, description="Organization node type"
    )
    allow_members: bool = Field(True, description="Whether members can be assigned")
    data_scope: str = Field(
        DataScope.DEPT_AND_CHILDREN.value,
        description="Organization authority scope policy",
    )
    custom_dept_ids: list[int] | None = Field(
        None,
        description="Custom organization node IDs used when data_scope=custom",
    )
    permission_ids: list[int] | None = Field(
        None,
        description="Assigned permission IDs",
    )


class TenantOrgNodeUpdateRequest(BaseSchema):
    """Update tenant org node request / 更新企业组织节点请求"""

    name: str | None = Field(
        None, min_length=1, max_length=50, description="Organization node name"
    )
    description: str | None = Field(
        None, max_length=500, description="Organization node description"
    )
    is_active: bool | None = Field(None, description="Whether the node is active")
    sort_order: int | None = Field(None, description="Sort order")
    parent_id: int | None = Field(None, description="Parent organization node ID")
    type: TenantOrgNodeType | None = Field(None, description="Organization node type")
    allow_members: bool | None = Field(
        None, description="Whether members can be assigned"
    )
    data_scope: str | None = Field(
        None, description="Organization authority scope policy"
    )
    custom_dept_ids: list[int] | None = Field(
        None,
        description="Custom organization node IDs used when data_scope=custom",
    )
    permission_ids: list[int] | None = Field(
        None,
        description="Assigned permission IDs",
    )


class TenantOrgNodeAuthorityPolicyRequest(BaseSchema):
    """Update tenant org node authority policy / 更新企业组织节点权限范围策略"""

    data_scope: str = Field(..., description="Organization authority scope policy")
    custom_dept_ids: list[int] | None = Field(
        None,
        description="Custom organization node IDs used when data_scope=custom",
    )


class TenantOrgNodeMoveRequest(BaseSchema):
    """Move tenant org node request / 移动企业组织节点请求"""

    new_parent_id: int | None = Field(
        None, description="New parent organization node ID"
    )


class TenantOrgNodeSetLeaderRequest(BaseSchema):
    """Set tenant org node leader / 设置企业组织节点负责人请求"""

    leader_id: int | None = Field(None, description="Leader tenant admin ID")


class TenantOrgNodeAssignMemberRequest(BaseSchema):
    """Assign tenant admin to org node / 分配企业管理员到组织节点请求"""

    admin_id: int = Field(..., description="Tenant admin ID")


class TenantOrgNodeCreateMemberRequest(BaseSchema):
    """Create tenant admin under org node / 在组织节点下创建企业管理员请求"""

    username: str = Field(..., min_length=2, max_length=50, description="Username")
    email: str = Field(..., description="Email")
    password: str = Field(..., min_length=6, max_length=50, description="Password")
    phone: str | None = Field(None, description="Phone")
    nickname: str | None = Field(None, description="Nickname")
    is_active: bool = Field(True, description="Whether the tenant admin is active")
    role_id: int | None = Field(None, description="Permission role ID")


class TenantOrgNodeUpdateMemberRequest(BaseSchema):
    """Update org node member / 更新组织节点成员请求"""

    email: str | None = Field(None, description="Email")
    phone: str | None = Field(None, description="Phone")
    nickname: str | None = Field(None, description="Nickname")
    avatar: str | None = Field(None, description="Avatar")
    is_active: bool | None = Field(
        None, description="Whether the tenant admin is active"
    )
    org_node_id: int | None = Field(None, description="New organization node ID")
    role_id: int | None = Field(None, description="Permission role ID")


class TenantOrgNodeResetPasswordRequest(BaseSchema):
    """Reset org node member password / 重置组织节点成员密码请求"""

    new_password: str = Field(
        ..., min_length=6, max_length=50, description="New password"
    )


class TenantOrgNodeToggleStatusRequest(BaseSchema):
    """Toggle org node member status / 切换组织节点成员状态请求"""

    is_active: bool = Field(..., description="Whether the tenant admin is active")


class TenantOrgNodeMemberResponse(BaseSchema):
    """Organization node member response / 组织节点成员响应"""

    id: int = Field(..., description="Tenant admin ID")
    username: str = Field(..., description="Username")
    nickname: str | None = Field(None, description="Nickname")
    avatar: str | None = Field(None, description="Avatar")
    email: str = Field(..., description="Email")
    is_active: bool = Field(True, description="Whether the tenant admin is active")
    is_leader: bool = Field(
        False, description="Whether the tenant admin is the node leader"
    )
    joined_at: datetime | None = Field(None, description="Joined at")
    org_node_id: int | None = Field(None, description="Organization node ID")
    org_node_name: str | None = Field(None, description="Organization node name")
    permission_role_id: int | None = Field(None, description="Permission role ID")
    permission_role_name: str | None = Field(None, description="Permission role name")
    created_at: datetime | None = Field(None, description="Created at")
    updated_at: datetime | None = Field(None, description="Updated at")


__all__ = [
    "TenantOrgNodeAssignMemberRequest",
    "TenantOrgNodeAuthorityPolicyRequest",
    "TenantOrgNodeCreateMemberRequest",
    "TenantOrgNodeCreateRequest",
    "TenantOrgNodeDetailResponse",
    "TenantOrgNodeLeaderResponse",
    "TenantOrgNodeMemberResponse",
    "TenantOrgNodeMoveRequest",
    "TenantOrgNodeResetPasswordRequest",
    "TenantOrgNodeResponse",
    "TenantOrgNodeSetLeaderRequest",
    "TenantOrgNodeToggleStatusRequest",
    "TenantOrgNodeType",
    "TenantOrgNodeUpdateMemberRequest",
    "TenantOrgNodeUpdateRequest",
]
