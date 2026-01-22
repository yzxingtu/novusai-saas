"""
租户管理员角色 API

提供租户端角色 CRUD、权限分配、层级管理等接口
"""

from fastapi import HTTPException, Query, Request, status

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.base_controller import TenantController
from app.core.base_schema import PageResponse
from app.core.deps import DbSession, ActiveTenantAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException, NotFoundException
from app.models import TenantAdmin, Permission
from app.models.auth.tenant_admin_role import TenantAdminRole
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.schemas.tenant import (
    TenantAdminRoleResponse,
    TenantAdminRoleDetailResponse,
    TenantAdminRoleCreateRequest,
    TenantAdminRoleUpdateRequest,
    TenantAdminRoleSetLeaderRequest,
    TenantAdminRoleAddMemberRequest,
    TenantAdminRoleMemberResponse,
)
from app.schemas.common import PermissionResponse, ReorderRequest
from app.services.tenant.tenant_admin_role_service import TenantAdminRoleService
from app.services.common.role_hierarchy_validator import TenantAdminRoleHierarchyValidator


@permission_resource(
    resource="organization",
    name="menu.tenant.organization",  # i18n key
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:git-branch",
        path="/system/organization",
        component="tenant/system/organization/index",
        parent="system",  # 父菜单: 权限管理
        sort_order=15,
    ),
)
class TenantRoleController(TenantController):
    """
    租户组织架构控制器
    
    提供组织架构 CRUD、权限分配、层级管理等接口
    """
    
    prefix = "/roles"
    tags = ["租户角色管理"]
    
    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router
        
        @router.get("/tree", summary="获取角色树")
        @action_read("action.organization.tree")
        async def get_role_tree(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取角色树形结构
            
            层级权限控制：
            - 租户所有者可以看到完整角色树
            - 普通管理员只能看到以自己角色为根的子树
            
            权限: role:tree
            """
            service = TenantAdminRoleService(db, current_admin.tenant_id)
            
            # 租户所有者可以看到完整树
            if current_admin.is_owner:
                tree = await service.get_tree()
                return success(data=tree, message=_("common.success"))
            
            # 普通管理员只能看到以自己角色为根的子树
            if current_admin.role_id is None:
                return success(data=[], message=_("common.success"))
            
            tree = await service.get_tree(parent_id=current_admin.role_id)
            return success(data=tree, message=_("common.success"))
        
        @router.get("/organization", summary="获取组织架构树（根节点）")
        @action_read("action.organization.organization")
        async def get_organization_tree(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取组织架构根节点列表（按需加载）
            
            层级权限控制：
            - 租户所有者：返回 level=1 的系统根节点
            - 普通管理员：返回自己所在角色作为根节点
            
            前端可通过 GET /roles/{id}/children 按需加载子节点。
            
            权限: role:organization
            """
            service = TenantAdminRoleService(db, current_admin.tenant_id)
            
            # 租户所有者可以看到完整组织架构
            if current_admin.is_owner:
                roles = await service.get_organization_root_nodes()
                return success(
                    data=[TenantAdminRoleResponse.model_validate(r, from_attributes=True) for r in roles],
                    message=_("common.success"),
                )
            
            # 普通管理员只能看到以自己角色为根的子树
            if current_admin.role_id is None:
                return success(data=[], message=_("common.success"))
            
            # 获取当前用户的角色作为根节点
            result = await db.execute(
                select(TenantAdminRole)
                .where(
                    TenantAdminRole.id == current_admin.role_id,
                    TenantAdminRole.tenant_id == current_admin.tenant_id,
                    TenantAdminRole.is_deleted == False,
                )
                .options(
                    selectinload(TenantAdminRole.children),
                    selectinload(TenantAdminRole.admins),
                )
            )
            role = result.scalar_one_or_none()
            
            if role is None:
                return success(data=[], message=_("common.success"))
            
            return success(
                data=[TenantAdminRoleResponse.model_validate(role, from_attributes=True)],
                message=_("common.success"),
            )
        
        # ========== 排序管理 API ==========
        
        @router.put("/reorder", summary="批量重排序")
        @action_update("action.organization.reorder")
        async def reorder_roles(
            request: Request,
            db: DbSession,
            data: ReorderRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            批量重排序组织架构节点
            
            接收有序的 ID 列表，按顺序重新分配排序值。
            
            层级权限控制：
            - 租户所有者：可重排所有节点
            - 普通管理员：只能重排自己可管理的节点
            
            请求示例:
                {
                    "ids": [3, 1, 5, 2, 4],
                    "parent_id": 1  // 可选，限定同级范围
                }
            
            权限: organization:reorder
            """
            service = TenantAdminRoleService(db, current_admin.tenant_id)
            validator = TenantAdminRoleHierarchyValidator(db, current_admin)
            
            # 非所有者需要校验每个节点的可管理性
            if not current_admin.is_owner:
                for role_id in data.ids:
                    if not await validator.can_manage_role(role_id):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=_("role.no_permission_to_manage"),
                        )
            
            try:
                updated_count = await service.reorder(
                    ordered_ids=data.ids,
                    tenant_id=current_admin.tenant_id,
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
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取角色详情（含权限列表）
            
            层级权限控制：只能查看可见角色的详情
            
            权限: role:detail
            """
            # 先查询角色是否存在
            result = await db.execute(
                select(TenantAdminRole)
                .where(
                    TenantAdminRole.id == role_id,
                    TenantAdminRole.tenant_id == current_admin.tenant_id,
                    TenantAdminRole.is_deleted == False,
                )
                .options(
                    selectinload(TenantAdminRole.permissions),
                    selectinload(TenantAdminRole.children),
                    selectinload(TenantAdminRole.admins),
                )
            )
            role = result.scalar_one_or_none()
            
            if role is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("role.not_found"),
                )
            
            # 校验角色可见性
            validator = TenantAdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_view_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_view"),
                )
            
            return success(
                data=TenantAdminRoleDetailResponse(
                    id=role.id,
                    tenant_id=role.tenant_id,
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
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取指定节点的直接子节点（用于按需加载组织架构树）
            
            层级权限控制：只能查看可见角色的子角色
            
            权限: role:children
            """
            # 校验角色可见性
            validator = TenantAdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_view_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_view"),
                )
            
            service = TenantAdminRoleService(db, current_admin.tenant_id)
            children = await service.get_organization_children(role_id)
            
            return success(
                data=[TenantAdminRoleResponse.model_validate(r, from_attributes=True) for r in children],
                message=_("common.success"),
            )
        
        @router.get("/{role_id}/permissions/effective", summary="获取有效权限")
        @action_read("action.organization.effective_permissions")
        async def get_effective_permissions(
            request: Request,
            db: DbSession,
            role_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取角色的有效权限（含继承的权限）
            
            层级权限控制：只能查看可见角色的有效权限
            
            权限: role:effective_permissions
            """
            # 校验角色可见性
            validator = TenantAdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_view_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_view"),
                )
            
            service = TenantAdminRoleService(db, current_admin.tenant_id)
            
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
            data: TenantAdminRoleCreateRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            创建租户角色
            
            层级权限控制：
            - 租户所有者可以在任何位置创建角色
            - 普通管理员只能在自己角色或其下级角色下创建
            - 只能分配自己已拥有的权限
            
            权限: role:create
            """
            validator = TenantAdminRoleHierarchyValidator(db, current_admin)
            
            # 校验父角色
            if not await validator.can_create_under_parent(data.parent_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.parent_must_be_visible"),
                )
            
            # 校验权限分配
            if data.permission_ids:
                unassignable = await validator.get_unassignable_permissions(data.permission_ids)
                if unassignable:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=_("role.cannot_assign_permission"),
                    )
            
            service = TenantAdminRoleService(db, current_admin.tenant_id)
            
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
                
                # 分配权限（只能分配租户端权限，且必须是自己拥有的）
                if data.permission_ids:
                    # 过滤只保留租户端权限
                    perm_result = await db.execute(
                        select(Permission.id).where(
                            Permission.id.in_(data.permission_ids),
                            Permission.scope.in_(["tenant", "both"]),
                            Permission.is_enabled == True,
                            Permission.is_deleted == False,
                        )
                    )
                    valid_perm_ids = [p for p in perm_result.scalars().all()]
                    if valid_perm_ids:
                        role = await service.assign_permissions(role.id, valid_perm_ids)
                
                await db.commit()
                
                # 重新加载角色以获取完整关联
                result = await db.execute(
                    select(TenantAdminRole)
                    .where(TenantAdminRole.id == role.id)
                    .options(
                        selectinload(TenantAdminRole.children),
                        selectinload(TenantAdminRole.admins),
                    )
                )
                role = result.scalar_one()
                
                return success(
                    data=TenantAdminRoleResponse.model_validate(role, from_attributes=True),
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
            data: TenantAdminRoleUpdateRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            更新租户角色
            
            层级权限控制：
            - 只能更新自己的下级角色
            - 只能分配自己已拥有的权限
            
            权限: role:update
            """
            validator = TenantAdminRoleHierarchyValidator(db, current_admin)
            
            # 校验角色可管理性
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )
            
            # 如果更新父角色，校验新父角色
            if data.parent_id is not None:
                if not await validator.can_create_under_parent(data.parent_id):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=_("role.parent_must_be_visible"),
                    )
            
            # 校验权限分配
            if data.permission_ids is not None:
                unassignable = await validator.get_unassignable_permissions(data.permission_ids)
                if unassignable:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=_("role.cannot_assign_permission"),
                    )
            
            service = TenantAdminRoleService(db, current_admin.tenant_id)
            
            try:
                # 构建更新数据
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
                
                # 更新权限（只能分配租户端权限，且必须是自己拥有的）
                if data.permission_ids is not None:
                    perm_result = await db.execute(
                        select(Permission.id).where(
                            Permission.id.in_(data.permission_ids),
                            Permission.scope.in_(["tenant", "both"]),
                            Permission.is_enabled == True,
                            Permission.is_deleted == False,
                        )
                    )
                    valid_perm_ids = [p for p in perm_result.scalars().all()]
                    role = await service.assign_permissions(role_id, valid_perm_ids)
                
                await db.commit()
                
                # 重新加载角色以获取完整关联
                result = await db.execute(
                    select(TenantAdminRole)
                    .where(TenantAdminRole.id == role.id)
                    .options(
                        selectinload(TenantAdminRole.children),
                        selectinload(TenantAdminRole.admins),
                    )
                )
                role = result.scalar_one()
                
                return success(
                    data=TenantAdminRoleResponse.model_validate(role, from_attributes=True),
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
            current_admin: ActiveTenantAdmin,
        ):
            """
            删除租户角色（软删除）
            
            层级权限控制：只能删除自己的下级角色
            
            删除前检查：
            - 系统内置角色不可删除
            - 有子角色的角色不可删除
            - 有关联用户的角色不可删除
            
            权限: role:delete
            """
            service = TenantAdminRoleService(db, current_admin.tenant_id)
            
            # 先检查角色是否存在
            role = await service.repo.get_by_id(role_id)
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("role.not_found"),
                )
            
            # 校验角色可管理性
            validator = TenantAdminRoleHierarchyValidator(db, current_admin)
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
        
        # ========== 组织架构管理 API ==========
        
        @router.get("/{role_id}/members", summary="获取节点成员列表")
        @action_read("action.organization.members")
        async def get_role_members(
            request: Request,
            db: DbSession,
            role_id: int,
            current_admin: ActiveTenantAdmin,
            search: str = Query("", description="搜索关键词（用户名/昵称/邮箱）"),
            page: int = Query(1, ge=1, alias="page[number]", description="页码"),
            page_size: int = Query(20, ge=1, le=100, alias="page[size]", description="每页数量"),
            include_descendants: bool = Query(True, description="是否包含子节点成员"),
        ):
            """
            获取节点成员列表（分页 + 搜索 + 递归子节点）
            
            - 支持通用搜索: search=xxx 模糊匹配用户名/昵称/邮箱
            - 支持分页: page[number]=1&page[size]=20
            - 支持递归查询: include_descendants=true 查询所有子节点成员
            
            权限: role:members
            """
            # 校验角色可见性
            validator = TenantAdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_view_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_view"),
                )
            
            service = TenantAdminRoleService(db, current_admin.tenant_id)
            
            try:
                # 获取角色信息（用于判断负责人）
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
                            TenantAdminRoleMemberResponse(
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
        
        @router.post("/{role_id}/members", summary="添加成员到节点")
        @action_update("action.organization.add_member")
        async def add_member_to_role(
            request: Request,
            db: DbSession,
            role_id: int,
            data: TenantAdminRoleAddMemberRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            添加成员到节点
            
            权限: role:add_member
            """
            # 校验角色可管理性
            validator = TenantAdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )
            
            service = TenantAdminRoleService(db, current_admin.tenant_id)
            
            try:
                role = await service.add_member(role_id, data.admin_id)
                await db.commit()
                
                # 返回成功消息，不返回完整角色数据（避免 session 断开后的懒加载问题）
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
            current_admin: ActiveTenantAdmin,
        ):
            """
            从节点移除成员
            
            权限: role:remove_member
            """
            # 校验角色可管理性
            validator = TenantAdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )
            
            service = TenantAdminRoleService(db, current_admin.tenant_id)
            
            try:
                role = await service.remove_member(role_id, admin_id)
                await db.commit()
                
                # 返回成功消息，不返回完整角色数据（避免 session 断开后的懒加载问题）
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
            data: TenantAdminRoleSetLeaderRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            设置节点负责人（仅部门类型可设置）
            
            权限: role:set_leader
            """
            # 校验角色可管理性
            validator = TenantAdminRoleHierarchyValidator(db, current_admin)
            if not await validator.can_manage_role(role_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )
            
            service = TenantAdminRoleService(db, current_admin.tenant_id)
            
            try:
                role = await service.set_leader(role_id, data.leader_id)
                await db.commit()
                
                # 返回成功消息，不返回完整角色数据（避免 session 断开后的懒加载问题）
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


# 导出路由器
router = TenantRoleController.get_router()

__all__ = ["router", "TenantRoleController"]
