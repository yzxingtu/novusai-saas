"""
平台管理员角色 API / Platform Admin Role API

提供平台端角色 CRUD、权限分配、层级管理等接口
Provides platform role CRUD, permission assignment, hierarchy management endpoints.
"""

from fastapi import HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException, NotFoundException
from app.models.auth.admin_role import AdminRole
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.repositories.system.admin_role_repository import AdminRoleRepository
from app.schemas.common import PermissionResponse, ReorderRequest
from app.schemas.system import (
    AdminRoleAddMemberRequest,
    AdminRoleCreateMemberRequest,
    AdminRoleCreateRequest,
    AdminRoleDetailResponse,
    AdminRoleMemberResponse,
    AdminRoleResetPasswordRequest,
    AdminRoleResponse,
    AdminRoleSetLeaderRequest,
    AdminRoleToggleStatusRequest,
    AdminRoleUpdateMemberRequest,
    AdminRoleUpdateRequest,
)
from app.services.common.role_hierarchy_validator import AdminRoleHierarchyValidator
from app.services.system.admin_role_service import AdminRoleService


@permission_resource(
    resource="organization",
    name="menu.admin.organization",  # i18n key
    scope=PermissionScope.ADMIN_ONLY,
    parent_resource="platform_mgmt",
    menu=MenuConfig(
        icon="lucide:git-branch",
        path="/system/organization",
        component="admin/system/organization/index",
        parent="system",  # 父菜单: 权限管理
        sort_order=15,
    )
)
class AdminRoleController(GlobalController):
    """
    平台组织架构控制器 / Platform Organization Controller

    提供组织架构 CRUD、权限分配、层级管理等接口
    Provides organization CRUD, permission assignment, hierarchy management endpoints.
    """

    prefix = "/roles"
    tags = ["Role Management (Platform)"]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("/tree", summary="获取角色树")
        @action_read("action.organization.tree")
        async def get_role_tree(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            获取角色树形结构 / Get role tree structure

            层级权限控制 / Hierarchy access control:
            - 超级管理员可以看到完整角色树 / Super admin can see the full role tree
            - 普通管理员只能看到以自己角色为根的子树 / Normal admin can only see subtree rooted at their own role

            权限 / Permission: role:tree
            """
            service = AdminRoleService(db)

            # 超级管理员可以看到完整树 / Super admin can see the full tree
            if current_admin.is_super:
                tree = await service.get_tree()
                return success(data=tree, message=_("common.success"))

            # 普通管理员只能看到以自己角色为根的子树 / Normal admin can only see subtree rooted at their role
            if current_admin.role_id is None:
                return success(data=[], message=_("common.success"))

            tree = await service.get_tree(parent_id=current_admin.role_id)
            return success(data=tree, message=_("common.success"))

        @router.get("/organization", summary="获取组织架构树（根节点）")
        @action_read("action.organization.organization")
        async def get_organization_tree(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            获取组织架构根节点列表（按需加载） / Get organization root nodes (lazy loading)

            层级权限控制 / Hierarchy access control:
            - 超级管理员：返回 level=1 的系统根节点 / Super admin: returns level=1 system root nodes
            - 普通管理员：返回自己所在角色作为根节点 / Normal admin: returns own role as root node

            前端可通过 GET /roles/{id}/children 按需加载子节点。
            Frontend can lazy-load children via GET /roles/{id}/children.

            权限 / Permission: role:organization
            """
            service = AdminRoleService(db)

            # 超级管理员可以看到完整组织架构 / Super admin can see the full organization
            if current_admin.is_super:
                roles = await service.get_organization_root_nodes()
                return success(
                    data=[AdminRoleResponse.model_validate(r, from_attributes=True) for r in roles],
                    message=_("common.success"),
                )

            # 普通管理员只能看到以自己角色为根的子树 / Normal admin can only see subtree rooted at their role
            if current_admin.role_id is None:
                return success(data=[], message=_("common.success"))

            # 获取当前用户的角色作为根节点 / Get current user's role as root node
            result = await db.execute(
                select(AdminRole)
                .where(
                    AdminRole.id == current_admin.role_id,
                    AdminRole.is_deleted.is_(False),
                )
                .options(
                    selectinload(AdminRole.children),
                    selectinload(AdminRole.admins),
                )
            )
            role = result.scalar_one_or_none()

            if role is None:
                return success(data=[], message=_("common.success"))

            return success(
                data=[AdminRoleResponse.model_validate(role, from_attributes=True)],
                message=_("common.success"),
            )

        # ========== 排序管理 API / Sorting Management API ==========

        @router.put("/reorder", summary="批量重排序")
        @action_update("action.organization.reorder")
        async def reorder_roles(
            request: Request,
            db: DbSession,
            data: ReorderRequest,
            current_admin: ActiveAdmin,
        ):
            """
            批量重排序组织架构节点 / Batch reorder organization nodes

            接收有序的 ID 列表，按顺序重新分配排序值。
            Receives an ordered ID list and reassigns sort values accordingly.

            层级权限控制 / Hierarchy access control:
            - 超级管理员：可重排所有节点 / Super admin: can reorder all nodes
            - 普通管理员：只能重排自己可管理的节点 / Normal admin: can only reorder manageable nodes

            请求示例 / Request example:
                {
                    "ids": [3, 1, 5, 2, 4],
                    "parent_id": 1  // 可选，限定同级范围 / Optional, restricts to siblings
                }

            权限 / Permission: organization:reorder
            """
            service = AdminRoleService(db)
            validator = AdminRoleHierarchyValidator(db, current_admin)

            # 非超管需要校验每个节点的可管理性 / Non-super admin must verify manageability of each node
            if not current_admin.is_super:
                for role_id in data.ids:
                    if not await validator.can_manage_role(role_id):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=_("role.no_permission_to_manage"),
                        )

            try:
                updated_count = await service.reorder(
                    ordered_ids=data.ids,
                    parent_id=data.parent_id,
                )
                await db.commit()

                return success(
                    data={"updated_count": updated_count},
                    message=_("common.reorder_success"),
                )

            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )

        @router.get("/{role_id}", summary="获取角色详情")
        @action_read("action.organization.detail")
        async def get_role(
            request: Request,
            db: DbSession,
            role_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            获取角色详情（含权限列表） / Get role details (with permission list)

            层级权限控制：只能查看可见角色的详情
            Hierarchy access control: can only view details of visible roles.

            权限 / Permission: role:detail
            """
            # 先查询角色是否存在 / Check if role exists
            result = await db.execute(
                select(AdminRole)
                .where(AdminRole.id == role_id, AdminRole.is_deleted.is_(False))
                .options(
                    selectinload(AdminRole.permissions),
                    selectinload(AdminRole.children),
                    selectinload(AdminRole.admins),
                )
            )
            role = result.scalar_one_or_none()

            if role is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("role.not_found"),
                )

            # 校验角色可见性 / Verify role visibility
            validator = AdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_view_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_view"),
                )

            return success(
                data=AdminRoleDetailResponse(
                    id=role.id,
                    code=role.code,
                    name=role.name,
                    description=role.description,
                    is_system=role.is_system,
                    is_active=role.is_active,
                    sort_order=role.sort_order,
                    parent_id=role.parent_id,
                    path=role.path,
                    level=role.level,
                    children_count=role.children_count,
                    has_children=role.has_children,
                    created_at=role.created_at,
                    permission_ids=[p.id for p in role.permissions],
                    permission_codes=[p.code for p in role.permissions],
                ),
                message=_("common.success"),
            )

        @router.get("/{role_id}/children", summary="获取子节点")
        @action_read("action.organization.children")
        async def get_role_children(
            request: Request,
            db: DbSession,
            role_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            获取指定节点的直接子节点（用于按需加载组织架构树） / Get direct children of a node (for lazy-loading organization tree)

            层级权限控制：只能查看可见角色的子角色
            Hierarchy access control: can only view children of visible roles.

            权限 / Permission: role:children
            """
            # 校验角色可见性 / Verify role visibility
            validator = AdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_view_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_view"),
                )

            service = AdminRoleService(db)
            children = await service.get_organization_children(role_id)

            return success(
                data=[AdminRoleResponse.model_validate(r, from_attributes=True) for r in children],
                message=_("common.success"),
            )

        @router.get("/{role_id}/permissions/effective", summary="获取有效权限")
        @action_read("action.organization.effective_permissions")
        async def get_effective_permissions(
            request: Request,
            db: DbSession,
            role_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            获取角色的有效权限（含继承的权限） / Get effective permissions of a role (including inherited)

            层级权限控制：只能查看可见角色的有效权限
            Hierarchy access control: can only view effective permissions of visible roles.

            权限 / Permission: role:effective_permissions
            """
            # 校验角色可见性 / Verify role visibility
            validator = AdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_view_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_view"),
                )

            service = AdminRoleService(db)

            try:
                permissions = await service.get_effective_permissions(role_id)
            except NotFoundException:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("role.not_found"),
                )

            return success(
                data=[PermissionResponse.model_validate(p, from_attributes=True) for p in permissions],
                message=_("common.success"),
            )

        @router.post("", summary="创建角色")
        @action_create("action.organization.create")
        async def create_role(
            request: Request,
            db: DbSession,
            data: AdminRoleCreateRequest,
            current_admin: ActiveAdmin,
        ):
            """
            创建平台角色 / Create platform role

            层级权限控制 / Hierarchy access control:
            - 超级管理员可以在任何位置创建角色 / Super admin can create roles anywhere
            - 普通管理员只能在自己角色或其下级角色下创建 / Normal admin can only create under own or subordinate roles
            - 只能分配自己已拥有的权限 / Can only assign permissions already owned

            权限 / Permission: role:create
            """
            validator = AdminRoleHierarchyValidator(db, current_admin)

            # 校验父角色 / Validate parent role
            if not await validator.can_create_under_parent(data.parent_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.parent_must_be_visible"),
                )

            # 校验权限分配 / Validate permission assignment
            if data.permission_ids:
                unassignable = await validator.get_unassignable_permissions(data.permission_ids)
                if unassignable:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=_("role.cannot_assign_permission"),
                    )

            service = AdminRoleService(db)

            try:
                role = await service.create_role(
                    name=data.name,
                    description=data.description,
                    is_active=data.is_active,
                    sort_order=data.sort_order,
                    parent_id=data.parent_id,
                    type=data.type,
                    allow_members=data.allow_members,
                )

                # 分配权限 / Assign permissions
                if data.permission_ids:
                    role = await service.assign_permissions(role.id, data.permission_ids)

                await db.commit()

                # 重新加载角色以获取完整关联 / Reload role to get full associations
                result = await db.execute(
                    select(AdminRole)
                    .where(AdminRole.id == role.id)
                    .options(
                        selectinload(AdminRole.children),
                        selectinload(AdminRole.admins),
                    )
                )
                role = result.scalar_one()

                return success(
                    data=AdminRoleResponse.model_validate(role, from_attributes=True),
                    message=_("role.created"),
                )

            except NotFoundException as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e.message),
                )
            except BusinessException as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e.message),
                )

        @router.put("/{role_id}", summary="更新角色")
        @action_update("action.organization.update")
        async def update_role(
            request: Request,
            db: DbSession,
            role_id: int,
            data: AdminRoleUpdateRequest,
            current_admin: ActiveAdmin,
        ):
            """
            更新平台角色 / Update platform role

            层级权限控制 / Hierarchy access control:
            - 只能更新自己的下级角色 / Can only update subordinate roles
            - 只能分配自己已拥有的权限 / Can only assign permissions already owned

            权限 / Permission: role:update
            """
            validator = AdminRoleHierarchyValidator(db, current_admin)

            # 校验角色可管理性 / Verify role manageability
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )

            # 如果更新父角色，校验新父角色 / If updating parent role, validate the new parent
            if data.parent_id is not None and not await validator.can_create_under_parent(data.parent_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.parent_must_be_visible"),
                )

            # 校验权限分配 / Validate permission assignment
            if data.permission_ids is not None:
                unassignable = await validator.get_unassignable_permissions(data.permission_ids)
                if unassignable:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=_("role.cannot_assign_permission"),
                    )

            service = AdminRoleService(db)

            try:
                # 构建更新数据 / Build update data
                update_data = {}
                if data.name is not None:
                    update_data["name"] = data.name
                if data.description is not None:
                    update_data["description"] = data.description
                if data.is_active is not None:
                    update_data["is_active"] = data.is_active
                if data.sort_order is not None:
                    update_data["sort_order"] = data.sort_order
                if data.parent_id is not None:
                    update_data["parent_id"] = data.parent_id

                role = await service.update_role(role_id, update_data)

                # 更新权限 / Update permissions
                if data.permission_ids is not None:
                    role = await service.assign_permissions(role_id, data.permission_ids)

                await db.commit()

                # 重新加载角色以获取完整关联 / Reload role to get full associations
                result = await db.execute(
                    select(AdminRole)
                    .where(AdminRole.id == role.id)
                    .options(
                        selectinload(AdminRole.children),
                        selectinload(AdminRole.admins),
                    )
                )
                role = result.scalar_one()

                return success(
                    data=AdminRoleResponse.model_validate(role, from_attributes=True),
                    message=_("role.updated"),
                )

            except NotFoundException as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e.message),
                )
            except BusinessException as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e.message),
                )

        @router.delete("/{role_id}", summary="删除角色")
        @action_delete("action.organization.delete")
        async def delete_role(
            request: Request,
            db: DbSession,
            role_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            删除平台角色（软删除） / Delete platform role (soft delete)

            层级权限控制：只能删除自己的下级角色
            Hierarchy access control: can only delete subordinate roles.

            删除前检查 / Pre-delete checks:
            - 系统内置角色不可删除 / System built-in roles cannot be deleted
            - 有子角色的角色不可删除 / Roles with children cannot be deleted
            - 有关联用户的角色不可删除 / Roles with associated users cannot be deleted

            权限 / Permission: role:delete
            """
            service = AdminRoleService(db)

            # 先检查角色是否存在 / Check if role exists
            role = await service.repo.get_by_id(role_id)
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("role.not_found"),
                )

            # 校验角色可管理性 / Verify role manageability
            validator = AdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )

            try:
                await service.delete_role(role_id)
                await db.commit()

                return success(
                    message=_("role.deleted"),
                )

            except NotFoundException as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e.message),
                )
            except BusinessException as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e.message),
                )

        # ========== 组织架构管理 API / Organization Management API ==========

        @router.get("/{role_id}/members", summary="获取节点成员列表")
        @action_read("action.organization.members")
        async def get_role_members(
            request: Request,
            db: DbSession,
            role_id: int,
            current_admin: ActiveAdmin,
            search: str = Query("", description="搜索关键词（用户名/昵称/邮箱）"),
            page: int = Query(1, ge=1, alias="page[number]", description="页码"),
            page_size: int = Query(20, ge=1, le=100, alias="page[size]", description="每页数量"),
            include_descendants: bool = Query(True, description="是否包含子节点成员"),
        ):
            """
            获取节点成员列表（分页 + 搜索 + 递归子节点） / Get node members (paginated + search + recursive children)

            - 支持通用搜索 / General search: search=xxx fuzzy match username/nickname/email
            - 支持分页 / Pagination: page[number]=1&page[size]=20
            - 支持递归查询 / Recursive query: include_descendants=true to query all descendant members

            权限 / Permission: role:members
            """
            # 校验角色可见性 / Verify role visibility
            validator = AdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_view_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_view"),
                )

            service = AdminRoleService(db)

            try:
                # 获取角色信息（用于判断负责人） / Get role info (to determine leader)
                role = await service.repo.get_by_id(role_id)
                if not role:
                    raise NotFoundException(message=_("role.not_found"))

                members, total = await service.get_members(
                    role_id,
                    search=search if search else None,
                    page=page,
                    page_size=page_size,
                    include_descendants=include_descendants,
                )

                return success(
                    data=PageResponse.create(
                        items=[
                            AdminRoleMemberResponse(
                                id=m.id,
                                username=m.username,
                                nickname=m.nickname,
                                avatar=m.avatar,
                                email=m.email,
                                is_active=m.is_active,
                                is_leader=(role.leader_id == m.id) if not include_descendants else (m.role and m.role.leader_id == m.id),
                                role_id=m.role_id,
                                role_name=m.role.name if m.role else None,
                                created_at=m.created_at,
                                updated_at=m.updated_at,
                            )
                            for m in members
                        ],
                        total=total,
                        page=page,
                        page_size=page_size,
                    ),
                    message=_("common.success"),
                )

            except NotFoundException as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e.message),
                )

        @router.post("/{role_id}/members/create", summary="在节点下创建成员")
        @action_create("action.organization.create_member")
        async def create_member_in_role(
            request: Request,
            db: DbSession,
            role_id: int,
            data: AdminRoleCreateMemberRequest,
            current_admin: ActiveAdmin,
        ):
            """
            在指定节点下创建新成员 / Create a new member under specified node

            创建新管理员并自动关联到指定角色/节点。
            Creates a new admin and automatically associates with the specified role/node.

            权限 / Permission: organization:create_member
            """
            # 校验角色可管理性 / Verify role manageability
            validator = AdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )

            service = AdminRoleService(db)

            try:
                admin = await service.create_member(
                    role_id=role_id,
                    username=data.username,
                    email=data.email,
                    password=data.password,
                    phone=data.phone,
                    nickname=data.nickname,
                    is_active=data.is_active,
                )
                await db.commit()

                # 返回创建的成员信息 / Return created member info
                return success(
                    data=AdminRoleMemberResponse(
                        id=admin.id,
                        username=admin.username,
                        nickname=admin.nickname,
                        avatar=admin.avatar,
                        email=admin.email,
                        is_active=admin.is_active,
                        is_leader=False,
                        role_id=admin.role_id,
                        role_name=None,  # 新创建时不需要角色名称
                        created_at=admin.created_at,
                        updated_at=admin.updated_at,
                    ),
                    message=_("role.member_created"),
                )

            except NotFoundException as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e.message),
                )
            except BusinessException as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e.message),
                )

        @router.put("/{role_id}/members/{admin_id}", summary="更新节点成员信息")
        @action_update("action.organization.update_member")
        async def update_member_in_role(
            request: Request,
            db: DbSession,
            role_id: int,
            admin_id: int,
            data: AdminRoleUpdateMemberRequest,
            current_admin: ActiveAdmin,
        ):
            """
            更新节点成员信息 / Update node member info

            支持修改成员的邮箱、手机号、昵称、状态，以及调整所属角色。
            Supports modifying member's email, phone, nickname, status, and adjusting role.

            权限 / Permission: organization:update_member
            """
            # 校验角色可管理性 / Verify role manageability
            validator = AdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )

            # 如果要调整到新角色，也需要校验新角色的可管理性 / If moving to a new role, also verify the new role's manageability
            if data.role_id is not None and not await validator.can_manage_role(data.role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )

            service = AdminRoleService(db)

            try:
                admin = await service.update_member(
                    role_id=role_id,
                    admin_id=admin_id,
                    email=data.email,
                    phone=data.phone,
                    nickname=data.nickname,
                    avatar=data.avatar,
                    is_active=data.is_active,
                    new_role_id=data.role_id,
                )
                await db.commit()

                # 重新加载管理员以获取角色信息 / Reload admin to get role info
                await db.refresh(admin)

                return success(
                    data=AdminRoleMemberResponse(
                        id=admin.id,
                        username=admin.username,
                        nickname=admin.nickname,
                        avatar=admin.avatar,
                        email=admin.email,
                        is_active=admin.is_active,
                        is_leader=False,
                        role_id=admin.role_id,
                        role_name=admin.role.name if admin.role else None,
                        created_at=admin.created_at,
                        updated_at=admin.updated_at,
                    ),
                    message=_("role.member_updated"),
                )

            except NotFoundException as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e.message),
                )
            except BusinessException as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e.message),
                )

        @router.put("/{role_id}/members/{admin_id}/reset-password", summary="重置节点成员密码")
        @action_update("action.organization.reset_password")
        async def reset_member_password(
            request: Request,
            db: DbSession,
            role_id: int,
            admin_id: int,
            data: AdminRoleResetPasswordRequest,
            current_admin: ActiveAdmin,
        ):
            """
            重置节点成员密码 / Reset node member password

            权限 / Permission: organization:reset_password
            """
            # 校验角色可管理性 / Verify role manageability
            validator = AdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )

            service = AdminRoleService(db)

            try:
                await service.reset_member_password(
                    role_id=role_id,
                    admin_id=admin_id,
                    new_password=data.new_password,
                )
                await db.commit()

                return success(
                    data={"success": True},
                    message=_("admin.password_reset"),
                )

            except NotFoundException as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e.message),
                )
            except BusinessException as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e.message),
                )

        @router.put("/{role_id}/members/{admin_id}/status", summary="切换节点成员状态")
        @action_update("action.organization.toggle_status")
        async def toggle_member_status(
            request: Request,
            db: DbSession,
            role_id: int,
            admin_id: int,
            data: AdminRoleToggleStatusRequest,
            current_admin: ActiveAdmin,
        ):
            """
            切换节点成员状态 / Toggle node member status

            权限 / Permission: organization:toggle_status
            """
            # 校验角色可管理性 / Verify role manageability
            validator = AdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )

            service = AdminRoleService(db)

            try:
                admin = await service.toggle_member_status(
                    role_id=role_id,
                    admin_id=admin_id,
                    is_active=data.is_active,
                )
                await db.commit()

                # 重新加载以获取角色信息 / Reload to get role info
                await db.refresh(admin)

                return success(
                    data=AdminRoleMemberResponse(
                        id=admin.id,
                        username=admin.username,
                        nickname=admin.nickname,
                        avatar=admin.avatar,
                        email=admin.email,
                        is_active=admin.is_active,
                        is_leader=False,
                        role_id=admin.role_id,
                        role_name=admin.role.name if admin.role else None,
                        created_at=admin.created_at,
                        updated_at=admin.updated_at,
                    ),
                    message=_("admin.status_updated"),
                )

            except NotFoundException as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e.message),
                )
            except BusinessException as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e.message),
                )

        @router.post("/{role_id}/members", summary="分配成员到节点")
        @action_update("action.organization.assign_member")
        async def assign_member_to_role(
            request: Request,
            db: DbSession,
            role_id: int,
            data: AdminRoleAddMemberRequest,
            current_admin: ActiveAdmin,
        ):
            """
            添加成员到节点 / Add member to node

            权限 / Permission: role:add_member
            """
            # 校验角色可管理性 / Verify role manageability
            validator = AdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )

            service = AdminRoleService(db)

            try:
                await service.add_member(role_id, data.admin_id)
                await db.commit()

                # 返回成功消息，不返回完整角色数据（避免 session 断开后的懒加载问题）
                # Return success message without full role data (avoid lazy loading issues after session disconnect)
                return success(
                    data={"role_id": role_id},
                    message=_("role.member_added"),
                )

            except NotFoundException as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e.message),
                )
            except BusinessException as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e.message),
                )

        @router.delete("/{role_id}/members/{admin_id}", summary="从节点移除成员")
        @action_update("action.organization.remove_member")
        async def remove_member_from_role(
            request: Request,
            db: DbSession,
            role_id: int,
            admin_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            从节点移除成员 / Remove member from node

            权限 / Permission: role:remove_member
            """
            # 校验角色可管理性 / Verify role manageability
            validator = AdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )

            service = AdminRoleService(db)

            try:
                await service.remove_member(role_id, admin_id)
                await db.commit()

                # 返回成功消息，不返回完整角色数据（避免 session 断开后的懒加载问题）
                # Return success message without full role data (avoid lazy loading issues after session disconnect)
                return success(
                    data={"role_id": role_id},
                    message=_("role.member_removed"),
                )

            except NotFoundException as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e.message),
                )
            except BusinessException as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e.message),
                )

        @router.put("/{role_id}/leader", summary="设置节点负责人")
        @action_update("action.organization.set_leader")
        async def set_role_leader(
            request: Request,
            db: DbSession,
            role_id: int,
            data: AdminRoleSetLeaderRequest,
            current_admin: ActiveAdmin,
        ):
            """
            设置节点负责人（仅部门类型可设置） / Set node leader (department type only)

            权限 / Permission: role:set_leader
            """
            # 校验角色可管理性 / Verify role manageability
            validator = AdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )

            # 禁止当前负责人自己修改负责人身份 / Prevent current leader from modifying their own leader status
            role = await AdminRoleRepository(db).get_by_id(role_id)
            if role and role.leader_id == current_admin.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.cannot_modify_own_leader_status"),
                )

            service = AdminRoleService(db)

            try:
                role = await service.set_leader(role_id, data.leader_id)
                await db.commit()

                # 返回成功消息，不返回完整角色数据（避免 session 断开后的懒加载问题）
                # Return success message without full role data (avoid lazy loading issues after session disconnect)
                return success(
                    data={"role_id": role_id, "leader_id": data.leader_id},
                    message=_("role.leader_set"),
                )

            except NotFoundException as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(e.message),
                )
            except BusinessException as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e.message),
                )


# 导出路由器 / Export router
router = AdminRoleController.get_router()

__all__ = ["router", "AdminRoleController"]
