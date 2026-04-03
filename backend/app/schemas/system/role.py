"""
Admin role schemas / 平台管理员角色 Schema

Defines platform admin role management request/response schemas with hierarchy,
member management, and data-scope fields.
定义平台管理员角色管理的请求/响应 Schema，覆盖层级结构、成员管理与数据权限字段。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.base_schema import BaseSchema
from app.enums.role import DataScope, RoleType


class AdminRoleResponse(BaseSchema):
    """Platform admin role response / 平台管理员角色响应。"""

    id: int = Field(..., description="角色 ID")
    code: str = Field(..., description="角色代码")
    name: str = Field(..., description="角色名称")
    description: str | None = Field(None, description="角色描述")
    is_system: bool = Field(..., description="是否系统内置")
    is_active: bool = Field(..., description="是否启用")
    sort_order: int = Field(0, description="排序")
    parent_id: int | None = Field(None, description="父角色 ID")
    path: str | None = Field(None, description="层级路径，如 /1/3/7/")
    level: int = Field(1, description="层级深度，根节点为 1")
    children_count: int = Field(0, description="子角色数量")
    has_children: bool = Field(False, description="是否有子角色")
    permissions_count: int = Field(0, description="权限数量")
    type: str = Field(
        RoleType.ROLE.value, description="节点类型: department/position/role"
    )
    allow_members: bool = Field(True, description="是否允许添加成员")
    leader_id: int | None = Field(None, description="负责人 ID")
    leader_name: str | None = Field(None, description="负责人名称")
    member_count: int = Field(0, description="成员数量")
    data_scope: str = Field(
        DataScope.SELF_ONLY.value,
        description="数据范围: all/dept_children/dept_only/self/custom",
    )
    custom_dept_ids: list[int] | None = Field(
        None,
        description="自定义部门 ID 列表（data_scope=custom 时生效）",
    )
    created_at: datetime = Field(..., description="创建时间")


class AdminRoleDetailResponse(AdminRoleResponse):
    """Platform admin role detail response / 平台管理员角色详情响应。"""

    permission_ids: list[int] = Field(default_factory=list, description="权限 ID 列表")
    permission_codes: list[str] = Field(
        default_factory=list, description="权限代码列表"
    )


class AdminRoleTreeNode(AdminRoleResponse):
    """Platform admin role tree node / 平台管理员角色树节点。"""

    children: list[AdminRoleTreeNode] = Field(
        default_factory=list, description="子角色列表"
    )


class AdminRoleCreateRequest(BaseSchema):
    """Create platform admin role request / 创建平台管理员角色请求。"""

    name: str = Field(..., min_length=1, max_length=50, description="角色名称")
    description: str | None = Field(None, max_length=500, description="角色描述")
    is_active: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, description="排序")
    parent_id: int | None = Field(None, description="父角色 ID，None 表示顶级角色")
    permission_ids: list[int] = Field(default_factory=list, description="权限 ID 列表")
    type: str = Field(
        RoleType.ROLE.value, description="节点类型: department/position/role"
    )
    allow_members: bool = Field(True, description="是否允许添加成员")
    data_scope: str = Field(
        DataScope.SELF_ONLY.value,
        description="数据范围: all/dept_children/dept_only/self/custom",
    )
    custom_dept_ids: list[int] | None = Field(
        None,
        description="自定义部门 ID 列表（data_scope=custom 时生效）",
    )


class AdminRoleUpdateRequest(BaseSchema):
    """Update platform admin role request / 更新平台管理员角色请求。"""

    name: str | None = Field(None, min_length=1, max_length=50, description="角色名称")
    description: str | None = Field(None, max_length=500, description="角色描述")
    is_active: bool | None = Field(None, description="是否启用")
    sort_order: int | None = Field(None, description="排序")
    parent_id: int | None = Field(None, description="父角色 ID")
    permission_ids: list[int] | None = Field(None, description="权限 ID 列表")
    type: str | None = Field(None, description="节点类型: department/position/role")
    allow_members: bool | None = Field(None, description="是否允许添加成员")
    leader_id: int | None = Field(None, description="负责人 ID")
    data_scope: str | None = Field(
        None,
        description="数据范围: all/dept_children/dept_only/self/custom",
    )
    custom_dept_ids: list[int] | None = Field(
        None,
        description="自定义部门 ID 列表（data_scope=custom 时生效）",
    )


class AdminRolePermissionsRequest(BaseSchema):
    """Assign platform admin role permissions request / 分配平台管理员角色权限请求。"""

    permission_ids: list[int] = Field(..., description="权限 ID 列表")


class AdminRoleMoveRequest(BaseSchema):
    """Move platform admin role node request / 移动平台管理员角色节点请求。"""

    new_parent_id: int | None = Field(
        None, description="新父角色 ID，None 表示移动到根级"
    )


class AdminRoleSetLeaderRequest(BaseSchema):
    """Set role leader request / 设置节点负责人请求。"""

    leader_id: int | None = Field(None, description="负责人 ID，None 表示取消负责人")


class AdminRoleAddMemberRequest(BaseSchema):
    """Assign existing admin to role / 分配已有管理员到节点请求。"""

    admin_id: int = Field(..., description="管理员 ID")


class AdminRoleCreateMemberRequest(BaseSchema):
    """Create member under role request / 在节点下创建成员请求。"""

    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    is_active: bool = Field(True, description="是否激活")


class AdminRoleUpdateMemberRequest(BaseSchema):
    """Update role member request / 更新节点成员请求。"""

    email: str | None = Field(None, description="邮箱")
    phone: str | None = Field(None, description="手机号")
    nickname: str | None = Field(None, description="昵称")
    avatar: str | None = Field(None, description="头像")
    is_active: bool | None = Field(None, description="是否激活")
    role_id: int | None = Field(None, description="新角色 ID（调整所属角色）")


class AdminRoleResetPasswordRequest(BaseSchema):
    """Reset role member password request / 重置节点成员密码请求。"""

    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")


class AdminRoleToggleStatusRequest(BaseSchema):
    """Toggle role member status request / 切换节点成员状态请求。"""

    is_active: bool = Field(..., description="是否激活")


class AdminRoleMemberResponse(BaseSchema):
    """Role member response / 节点成员响应。"""

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
    "AdminRoleSetLeaderRequest",
    "AdminRoleAddMemberRequest",
    "AdminRoleCreateMemberRequest",
    "AdminRoleUpdateMemberRequest",
    "AdminRoleResetPasswordRequest",
    "AdminRoleToggleStatusRequest",
    "AdminRoleMemberResponse",
]
