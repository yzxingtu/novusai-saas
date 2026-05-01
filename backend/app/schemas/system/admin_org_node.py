"""
Admin organization node schemas / 管理后台组织节点 Schema
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.base_schema import BaseSchema
from app.enums.role import DataScope, RoleType

AdminOrgNodeType = Literal["department", "position"]


class AdminOrgNodeLeaderResponse(BaseSchema):
    """Leader info for organization node / 组织节点负责人信息"""

    id: int = Field(..., description="Leader admin ID")
    username: str = Field(..., description="Leader username")
    nickname: str | None = Field(None, description="Leader nickname")
    real_name: str | None = Field(None, description="Leader display name")
    avatar: str | None = Field(None, description="Leader avatar")


class AdminOrgNodeResponse(BaseSchema):
    """Admin organization node response / 管理后台组织节点响应"""

    id: int = Field(..., description="Organization node ID")
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
    allow_members: bool = Field(True, description="Whether members can be assigned")
    leader_id: int | None = Field(None, description="Leader admin ID")
    leader: AdminOrgNodeLeaderResponse | None = Field(None, description="Leader info")
    member_count: int = Field(0, description="Direct member count")
    permissions_count: int = Field(0, description="Direct permission count")
    data_scope: str = Field(
        DataScope.DEPT_AND_CHILDREN.value,
        description="Organization data scope",
    )
    custom_dept_ids: list[int] | None = Field(
        None,
        description="Custom organization node IDs when data_scope=custom",
    )
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime | None = Field(None, description="Updated at")


class AdminOrgNodeDetailResponse(AdminOrgNodeResponse):
    """Admin organization node detail response / 管理后台组织节点详情响应"""

    permission_ids: list[int] = Field(
        default_factory=list, description="Assigned permission IDs"
    )
    permission_codes: list[str] = Field(
        default_factory=list, description="Assigned permission codes"
    )


class AdminOrgNodeTreeNode(AdminOrgNodeResponse):
    """Admin organization tree node / 管理后台组织树节点"""

    children: list[AdminOrgNodeTreeNode] = Field(
        default_factory=list, description="Child nodes"
    )


class AdminOrgNodeCreateRequest(BaseSchema):
    """Create admin organization node request / 创建管理后台组织节点请求"""

    name: str = Field(
        ..., min_length=1, max_length=50, description="Organization node name"
    )
    description: str | None = Field(
        None, max_length=500, description="Organization node description"
    )
    is_active: bool = Field(True, description="Whether the node is active")
    sort_order: int = Field(0, description="Sort order")
    parent_id: int | None = Field(None, description="Parent organization node ID")
    type: AdminOrgNodeType = Field(
        RoleType.DEPARTMENT.value, description="Organization node type"
    )
    allow_members: bool = Field(True, description="Whether members can be assigned")
    data_scope: str = Field(
        DataScope.DEPT_AND_CHILDREN.value,
        description="Organization data scope",
    )
    custom_dept_ids: list[int] | None = Field(
        None,
        description="Custom organization node IDs when data_scope=custom",
    )
    permission_ids: list[int] | None = Field(
        None,
        description="Assigned permission IDs",
    )


class AdminOrgNodeUpdateRequest(BaseSchema):
    """Update admin organization node request / 更新管理后台组织节点请求"""

    name: str | None = Field(
        None, min_length=1, max_length=50, description="Organization node name"
    )
    description: str | None = Field(
        None, max_length=500, description="Organization node description"
    )
    is_active: bool | None = Field(None, description="Whether the node is active")
    sort_order: int | None = Field(None, description="Sort order")
    parent_id: int | None = Field(None, description="Parent organization node ID")
    type: AdminOrgNodeType | None = Field(None, description="Organization node type")
    allow_members: bool | None = Field(
        None, description="Whether members can be assigned"
    )
    data_scope: str | None = Field(None, description="Organization data scope")
    custom_dept_ids: list[int] | None = Field(
        None,
        description="Custom organization node IDs when data_scope=custom",
    )
    permission_ids: list[int] | None = Field(
        None,
        description="Assigned permission IDs",
    )


class AdminOrgNodeAuthorityPolicyRequest(BaseSchema):
    """Update admin organization authority policy / 更新管理后台组织权限范围策略"""

    data_scope: str = Field(..., description="Organization data scope")
    custom_dept_ids: list[int] | None = Field(
        None,
        description="Custom organization node IDs when data_scope=custom",
    )


class AdminOrgNodeMoveRequest(BaseSchema):
    """Move admin organization node request / 移动管理后台组织节点请求"""

    new_parent_id: int | None = Field(
        None, description="New parent organization node ID"
    )


class AdminOrgNodeSetLeaderRequest(BaseSchema):
    """Set admin organization node leader / 设置管理后台组织节点负责人请求"""

    leader_id: int | None = Field(None, description="Leader admin ID")


class AdminOrgNodeAssignMemberRequest(BaseSchema):
    """Assign admin to organization node / 分配管理员到组织节点请求"""

    admin_id: int = Field(..., description="Admin ID")


class AdminOrgNodeCreateMemberRequest(BaseSchema):
    """Create admin directly under organization node / 在组织节点下创建管理员请求"""

    username: str = Field(..., min_length=2, max_length=50, description="Username")
    email: str = Field(..., description="Email")
    password: str = Field(..., min_length=6, max_length=50, description="Password")
    phone: str | None = Field(None, description="Phone")
    nickname: str | None = Field(None, description="Nickname")
    is_active: bool = Field(True, description="Whether the admin is active")
    ai_enabled: bool = Field(True, description="Whether AI chat is enabled")


class AdminOrgNodeUpdateMemberRequest(BaseSchema):
    """Update organization node member / 更新组织节点成员请求"""

    email: str | None = Field(None, description="Email")
    phone: str | None = Field(None, description="Phone")
    nickname: str | None = Field(None, description="Nickname")
    avatar: str | None = Field(None, description="Avatar")
    is_active: bool | None = Field(None, description="Whether the admin is active")
    ai_enabled: bool | None = Field(None, description="Whether AI chat is enabled")
    org_node_id: int | None = Field(None, description="New organization node ID")


class AdminOrgNodeResetPasswordRequest(BaseSchema):
    """Reset organization node member password / 重置组织节点成员密码请求"""

    new_password: str = Field(
        ..., min_length=6, max_length=50, description="New password"
    )


class AdminOrgNodeToggleStatusRequest(BaseSchema):
    """Toggle organization node member status / 切换组织节点成员状态请求"""

    is_active: bool = Field(..., description="Whether the admin is active")


class AdminOrgNodeMemberResponse(BaseSchema):
    """Organization node member response / 组织节点成员响应"""

    id: int = Field(..., description="Admin ID")
    username: str = Field(..., description="Username")
    nickname: str | None = Field(None, description="Nickname")
    avatar: str | None = Field(None, description="Avatar")
    email: str = Field(..., description="Email")
    is_active: bool = Field(True, description="Whether the admin is active")
    ai_enabled: bool = Field(True, description="Whether AI chat is enabled")
    is_leader: bool = Field(False, description="Whether the admin is the node leader")
    joined_at: datetime | None = Field(None, description="Joined at")
    role_id: int | None = Field(None, description="Permission role ID")
    role_name: str | None = Field(None, description="Permission role name")
    org_node_id: int | None = Field(None, description="Organization node ID")
    org_node_name: str | None = Field(None, description="Organization node name")
    permission_role_id: int | None = Field(None, description="Permission role ID")
    permission_role_name: str | None = Field(None, description="Permission role name")
    created_at: datetime | None = Field(None, description="Created at")
    updated_at: datetime | None = Field(None, description="Updated at")


__all__ = [
    "AdminOrgNodeAssignMemberRequest",
    "AdminOrgNodeAuthorityPolicyRequest",
    "AdminOrgNodeCreateMemberRequest",
    "AdminOrgNodeCreateRequest",
    "AdminOrgNodeDetailResponse",
    "AdminOrgNodeLeaderResponse",
    "AdminOrgNodeMemberResponse",
    "AdminOrgNodeMoveRequest",
    "AdminOrgNodeResetPasswordRequest",
    "AdminOrgNodeResponse",
    "AdminOrgNodeSetLeaderRequest",
    "AdminOrgNodeToggleStatusRequest",
    "AdminOrgNodeTreeNode",
    "AdminOrgNodeType",
    "AdminOrgNodeUpdateMemberRequest",
    "AdminOrgNodeUpdateRequest",
]
