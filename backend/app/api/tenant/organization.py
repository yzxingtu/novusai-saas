"""
Tenant organization APIs / 企业后台组织节点 API
"""

from __future__ import annotations

from fastapi import HTTPException, Query, Request, status

from app.api.shared._ai_account_guard import (
    ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
    register_ai_switch_operation_permission,
    resolve_authorized_ai_enabled_override,
)
from app.api.shared._organization_helpers import (
    await_or_raise_http,
    commit_or_raise_http,
    serialize_organization_tree,
)
from app.core.base_controller import TenantController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.recycle_bin import register_tenant_recycle_bin_routes
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuAIConfig,
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.common import ReorderRequest
from app.schemas.tenant.tenant_org_node import (
    TenantOrgNodeAssignMemberRequest,
    TenantOrgNodeAuthorityPolicyRequest,
    TenantOrgNodeCreateMemberRequest,
    TenantOrgNodeCreateRequest,
    TenantOrgNodeDetailResponse,
    TenantOrgNodeLeaderResponse,
    TenantOrgNodeMemberResponse,
    TenantOrgNodeMoveRequest,
    TenantOrgNodeResetPasswordRequest,
    TenantOrgNodeResponse,
    TenantOrgNodeSetLeaderRequest,
    TenantOrgNodeToggleStatusRequest,
    TenantOrgNodeUpdateMemberRequest,
    TenantOrgNodeUpdateRequest,
)
from app.services.tenant.tenant_org_authority_service import TenantOrgAuthorityService
from app.services.tenant.tenant_org_node_service import TenantOrgNodeService


def _serialize_leader(leader) -> TenantOrgNodeLeaderResponse | None:
    if not leader or getattr(leader, "is_deleted", False):
        return None
    return TenantOrgNodeLeaderResponse(
        id=leader.id,
        username=leader.username,
        nickname=leader.nickname,
        real_name=None,
        avatar=leader.avatar,
    )


def _serialize_org_node(org_node) -> TenantOrgNodeResponse:
    return TenantOrgNodeResponse(
        id=org_node.id,
        tenant_id=org_node.tenant_id,
        code=org_node.code,
        name=org_node.name,
        description=org_node.description,
        is_system=org_node.is_system,
        is_active=org_node.is_active,
        sort_order=org_node.sort_order,
        parent_id=org_node.parent_id,
        path=org_node.path,
        level=org_node.level,
        children_count=getattr(org_node, "children_count", 0),
        has_children=getattr(org_node, "has_children", False),
        type=org_node.type,
        allow_members=org_node.allow_members,
        leader_id=getattr(org_node, "leader_id", None),
        leader=_serialize_leader(getattr(org_node, "leader", None)),
        leader_name=getattr(org_node, "leader_name", None),
        member_count=getattr(org_node, "member_count", 0),
        permissions_count=getattr(org_node, "permissions_count", 0),
        data_scope=getattr(org_node, "scope_mode", None) or "dept_children",
        custom_dept_ids=getattr(org_node, "custom_org_node_ids", None),
        created_at=org_node.created_at,
        updated_at=org_node.updated_at,
    )


def _serialize_org_node_detail(
    org_node,
    *,
    can_assign_permissions: bool,
) -> TenantOrgNodeDetailResponse:
    permissions = [
        permission
        for permission in getattr(org_node, "permissions", [])
        if permission.is_enabled and not permission.is_deleted
    ]
    return TenantOrgNodeDetailResponse(
        **_serialize_org_node(org_node).model_dump(),
        permission_ids=[permission.id for permission in permissions],
        permission_codes=[permission.code for permission in permissions],
        can_assign_permissions=can_assign_permissions,
    )


def _serialize_member(member) -> TenantOrgNodeMemberResponse:
    org_relation = getattr(member, "org_node", None)
    permission_role = getattr(member, "role", None)
    is_leader = (
        org_relation is not None
        and getattr(org_relation, "leader_id", None) == member.id
    )
    return TenantOrgNodeMemberResponse(
        id=member.id,
        username=member.username,
        nickname=member.nickname,
        avatar=member.avatar,
        email=member.email,
        is_active=member.is_active,
        ai_enabled=getattr(member, "ai_enabled", True),
        is_leader=is_leader,
        joined_at=member.created_at,
        org_node_id=getattr(member, "org_node_id", None),
        org_node_name=getattr(org_relation, "name", None),
        permission_role_id=getattr(member, "role_id", None),
        permission_role_name=getattr(permission_role, "name", None),
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


@permission_resource(
    resource="organization",
    name="menu.tenant.organization",
    scope=PermissionScope.TENANT,
    parent_resource="system",
    menu=MenuConfig(
        ai=MenuAIConfig(
            description="Manage organization structure, departments, members, and leaders",
            keywords=[
                "组织",
                "组织架构",
                "部门",
                "成员",
                "organization",
                "org",
                "team",
            ],
            capabilities=[
                "create_org_node",
                "edit_org_node",
                "assign_members",
                "view_organization",
            ],
            category="organization",
        ),
        icon="lucide:git-branch",
        path="/system/organization",
        component="tenant/system/organization/index",
        parent="system",
        sort_order=15,
    ),
)
class TenantOrganizationController(TenantController):
    """Tenant org node controller / 企业组织节点控制器"""

    prefix = "/organization"
    tags = ["Organization Management (Tenant)"]

    async def _require_view(
        self, db: DbSession, tenant_admin: ActiveTenantAdmin, org_node_id: int
    ) -> None:
        if not await TenantOrgAuthorityService(db, tenant_admin).can_view_org_node(
            org_node_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_("role.no_permission_to_view"),
            )

    async def _require_manage(
        self, db: DbSession, tenant_admin: ActiveTenantAdmin, org_node_id: int
    ) -> None:
        if not await TenantOrgAuthorityService(db, tenant_admin).can_manage_org_node(
            org_node_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_("role.no_permission_to_manage"),
            )

    def _register_routes(self) -> None:
        router = self.router

        @router.get("/tree", summary="获取组织树")
        @action_read("action.organization.tree")
        async def get_org_tree(
            request: Request, db: DbSession, current_admin: ActiveTenantAdmin
        ):
            service = TenantOrgNodeService(db, current_admin.tenant_id)
            authority = TenantOrgAuthorityService(db, current_admin)
            if current_admin.is_owner:
                return success(
                    data=serialize_organization_tree(
                        await service.get_visible_org_tree(),
                        lambda node: _serialize_org_node(node).model_dump(),
                    ),
                    message=_("common.success"),
                )

            scope_ids = await authority.get_visible_org_node_ids()
            return success(
                data=serialize_organization_tree(
                    await service.get_visible_org_tree(scope_ids),
                    lambda node: _serialize_org_node(node).model_dump(),
                ),
                message=_("common.success"),
            )

        @router.get("", summary="获取组织根节点")
        @action_read("action.organization.organization")
        async def get_org_roots(
            request: Request, db: DbSession, current_admin: ActiveTenantAdmin
        ):
            service = TenantOrgNodeService(db, current_admin.tenant_id)
            authority = TenantOrgAuthorityService(db, current_admin)
            if current_admin.is_owner:
                nodes = await service.get_visible_root_nodes()
                return success(
                    data=[_serialize_org_node(node) for node in nodes],
                    message=_("common.success"),
                )

            scope_ids = await authority.get_visible_org_node_ids()
            items = await service.get_visible_root_nodes(scope_ids)
            return success(
                data=[_serialize_org_node(node) for node in items],
                message=_("common.success"),
            )

        @router.put("/reorder", summary="批量重排序组织节点")
        @action_update("action.organization.reorder")
        async def reorder_org_nodes(
            request: Request,
            db: DbSession,
            data: ReorderRequest,
            current_admin: ActiveTenantAdmin,
        ):
            authority = TenantOrgAuthorityService(db, current_admin)
            if not current_admin.is_owner:
                for org_node_id in data.ids:
                    if not await authority.can_manage_org_node(org_node_id):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=_("role.no_permission_to_manage"),
                        )
            updated_count = await TenantOrgNodeService(
                db, current_admin.tenant_id
            ).reorder(
                ordered_ids=data.ids,
                parent_id=data.parent_id,
            )
            await db.commit()
            return success(
                data={"updated_count": updated_count},
                message=_("common.reorder_success"),
            )

        @router.get("/{org_node_id}", summary="获取组织节点详情")
        @action_read("action.organization.detail")
        async def get_org_node(
            request: Request,
            db: DbSession,
            org_node_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_view(db, current_admin, org_node_id)
            authority = TenantOrgAuthorityService(db, current_admin)
            org_node = await TenantOrgNodeService(
                db,
                current_admin.tenant_id,
            ).get_org_node_detail(org_node_id)
            return success(
                data=_serialize_org_node_detail(
                    org_node,
                    can_assign_permissions=await authority.can_assign_permissions_for_node(
                        org_node_id
                    ),
                ),
                message=_("common.success"),
            )

        @router.get("/{org_node_id}/children", summary="获取组织子节点")
        @action_read("action.organization.children")
        async def get_org_children(
            request: Request,
            db: DbSession,
            org_node_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_view(db, current_admin, org_node_id)
            nodes = await TenantOrgNodeService(
                db, current_admin.tenant_id
            ).get_organization_children(org_node_id)
            return success(
                data=[_serialize_org_node(node) for node in nodes],
                message=_("common.success"),
            )

        @router.post("", summary="创建组织节点")
        @action_create("action.organization.create")
        async def create_org_node(
            request: Request,
            db: DbSession,
            data: TenantOrgNodeCreateRequest,
            current_admin: ActiveTenantAdmin,
        ):
            if not await TenantOrgAuthorityService(
                db, current_admin
            ).can_create_under_parent(data.parent_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.parent_must_be_visible"),
                )
            if data.permission_ids is not None and not await TenantOrgAuthorityService(
                db, current_admin
            ).can_assign_permissions_for_node(data.parent_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )
            org_node = await commit_or_raise_http(
                db,
                TenantOrgNodeService(db, current_admin.tenant_id).create_org_node(
                    **data.model_dump()
                ),
            )
            return success(
                data=_serialize_org_node(org_node), message=_("role.created")
            )

        @router.put("/{org_node_id}", summary="更新组织节点")
        @action_update("action.organization.update")
        async def update_org_node(
            request: Request,
            db: DbSession,
            org_node_id: int,
            data: TenantOrgNodeUpdateRequest,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            authority = TenantOrgAuthorityService(db, current_admin)
            if (
                "parent_id" in data.model_fields_set
                and not await authority.can_create_under_parent(data.parent_id)
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.parent_must_be_visible"),
                )
            if (
                "permission_ids" in data.model_fields_set
                and not await authority.can_assign_permissions_for_node(org_node_id)
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.no_permission_to_manage"),
                )
            org_node = await commit_or_raise_http(
                db,
                TenantOrgNodeService(db, current_admin.tenant_id).update_org_node(
                    org_node_id,
                    data.model_dump(exclude_unset=True),
                ),
            )
            return success(
                data=_serialize_org_node(org_node), message=_("role.updated")
            )

        @router.put("/{org_node_id}/move", summary="移动组织节点")
        @action_update("action.organization.move")
        async def move_org_node(
            request: Request,
            db: DbSession,
            org_node_id: int,
            data: TenantOrgNodeMoveRequest,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            if not await TenantOrgAuthorityService(
                db, current_admin
            ).can_create_under_parent(data.new_parent_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.parent_must_be_visible"),
                )
            org_node = await commit_or_raise_http(
                db,
                TenantOrgNodeService(db, current_admin.tenant_id).move_org_node(
                    org_node_id,
                    data.new_parent_id,
                ),
            )
            return success(data=_serialize_org_node(org_node), message=_("role.moved"))

        @router.put("/{org_node_id}/authority", summary="更新组织权限范围策略")
        @action_update("action.organization.update_authority")
        async def update_org_authority(
            request: Request,
            db: DbSession,
            org_node_id: int,
            data: TenantOrgNodeAuthorityPolicyRequest,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            org_node = await commit_or_raise_http(
                db,
                TenantOrgNodeService(
                    db, current_admin.tenant_id
                ).update_authority_policy(
                    org_node_id,
                    data_scope=data.data_scope,
                    custom_dept_ids=data.custom_dept_ids,
                ),
            )
            return success(
                data=_serialize_org_node(org_node), message=_("role.updated")
            )

        @router.delete("/{org_node_id}", summary="删除组织节点")
        @action_delete("action.organization.delete")
        async def delete_org_node(
            request: Request,
            db: DbSession,
            org_node_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            await commit_or_raise_http(
                db,
                TenantOrgNodeService(db, current_admin.tenant_id).delete_org_node(
                    org_node_id
                ),
            )
            return success(data={"id": org_node_id}, message=_("role.deleted"))

        @router.get("/{org_node_id}/members", summary="获取组织节点成员")
        @action_read("action.organization.members")
        async def get_org_members(
            request: Request,
            db: DbSession,
            org_node_id: int,
            current_admin: ActiveTenantAdmin,
            search: str = Query("", description=_("api.param.search")),
            page: int = Query(
                1, alias="page[number]", ge=1, description=_("api.param.page_number")
            ),
            page_size: int = Query(
                20,
                alias="page[size]",
                ge=1,
                le=100,
                description=_("api.param.page_size"),
            ),
            include_descendants: bool = Query(
                True, description=_("api.param.include_descendants")
            ),
        ):
            await self._require_view(db, current_admin, org_node_id)
            members, total = await await_or_raise_http(
                TenantOrgNodeService(db, current_admin.tenant_id).get_members(
                    org_node_id,
                    search=search or None,
                    page=page,
                    page_size=page_size,
                    include_descendants=include_descendants,
                )
            )
            return success(
                data=PageResponse.create(
                    items=[_serialize_member(member) for member in members],
                    total=total,
                    page=page,
                    page_size=page_size,
                ),
                message=_("common.success"),
            )

        @router.post("/{org_node_id}/members/create", summary="在组织节点下创建成员")
        @action_create("action.organization.create_member")
        async def create_member(
            request: Request,
            db: DbSession,
            org_node_id: int,
            data: TenantOrgNodeCreateMemberRequest,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            await resolve_authorized_ai_enabled_override(
                request=request,
                data=data,
                permission_code=ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
            )
            admin = await commit_or_raise_http(
                db,
                TenantOrgNodeService(db, current_admin.tenant_id).create_member(
                    org_node_id=org_node_id,
                    username=data.username,
                    email=data.email,
                    password=data.password,
                    phone=data.phone,
                    nickname=data.nickname,
                    is_active=data.is_active,
                    ai_enabled=data.ai_enabled,
                    role_id=data.role_id,
                ),
            )
            return success(
                data=_serialize_member(admin), message=_("role.member_created")
            )

        @router.put("/{org_node_id}/members/{admin_id}", summary="更新组织节点成员")
        @action_update("action.organization.update_member")
        async def update_member(
            request: Request,
            db: DbSession,
            org_node_id: int,
            admin_id: int,
            data: TenantOrgNodeUpdateMemberRequest,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            if data.org_node_id is not None:
                await self._require_manage(db, current_admin, data.org_node_id)
            await resolve_authorized_ai_enabled_override(
                request=request,
                data=data,
                permission_code=ORGANIZATION_MANAGE_MEMBER_AI_PERMISSION,
            )
            update_permission_role = "role_id" in data.model_fields_set
            admin = await commit_or_raise_http(
                db,
                TenantOrgNodeService(db, current_admin.tenant_id).update_member(
                    org_node_id=org_node_id,
                    admin_id=admin_id,
                    email=data.email,
                    phone=data.phone,
                    nickname=data.nickname,
                    avatar=data.avatar,
                    is_active=data.is_active,
                    ai_enabled=data.ai_enabled,
                    update_ai_enabled="ai_enabled" in data.model_fields_set,
                    new_org_node_id=data.org_node_id,
                    role_id=data.role_id,
                    update_permission_role=update_permission_role,
                ),
            )
            return success(
                data=_serialize_member(admin), message=_("role.member_updated")
            )

        @router.put(
            "/{org_node_id}/members/{admin_id}/reset-password",
            summary="重置组织节点成员密码",
        )
        @action_update("action.organization.reset_password")
        async def reset_member_password(
            request: Request,
            db: DbSession,
            org_node_id: int,
            admin_id: int,
            data: TenantOrgNodeResetPasswordRequest,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            await commit_or_raise_http(
                db,
                TenantOrgNodeService(db, current_admin.tenant_id).reset_member_password(
                    org_node_id,
                    admin_id,
                    data.new_password,
                ),
            )
            return success(
                data={"success": True}, message=_("tenant_admin.password_reset")
            )

        @router.put(
            "/{org_node_id}/members/{admin_id}/status", summary="切换组织节点成员状态"
        )
        @action_update("action.organization.toggle_status")
        async def toggle_member_status(
            request: Request,
            db: DbSession,
            org_node_id: int,
            admin_id: int,
            data: TenantOrgNodeToggleStatusRequest,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            admin = await commit_or_raise_http(
                db,
                TenantOrgNodeService(db, current_admin.tenant_id).toggle_member_status(
                    org_node_id,
                    admin_id,
                    data.is_active,
                ),
            )
            return success(
                data=_serialize_member(admin),
                message=_("tenant_admin.status_updated"),
            )

        @router.post("/{org_node_id}/members", summary="分配成员到组织节点")
        @action_update("action.organization.assign_member")
        async def assign_member(
            request: Request,
            db: DbSession,
            org_node_id: int,
            data: TenantOrgNodeAssignMemberRequest,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            admin = await commit_or_raise_http(
                db,
                TenantOrgNodeService(db, current_admin.tenant_id).add_member(
                    org_node_id, data.admin_id
                ),
            )
            return success(
                data=_serialize_member(admin), message=_("role.member_added")
            )

        @router.delete(
            "/{org_node_id}/members/{admin_id}", summary="从组织节点移除成员"
        )
        @action_update("action.organization.remove_member")
        async def remove_member(
            request: Request,
            db: DbSession,
            org_node_id: int,
            admin_id: int,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            admin = await commit_or_raise_http(
                db,
                TenantOrgNodeService(db, current_admin.tenant_id).remove_member(
                    org_node_id, admin_id
                ),
            )
            return success(
                data=_serialize_member(admin), message=_("role.member_removed")
            )

        @router.put("/{org_node_id}/leader", summary="设置组织节点负责人")
        @action_update("action.organization.set_leader")
        async def set_leader(
            request: Request,
            db: DbSession,
            org_node_id: int,
            data: TenantOrgNodeSetLeaderRequest,
            current_admin: ActiveTenantAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            org_node = await commit_or_raise_http(
                db,
                TenantOrgNodeService(db, current_admin.tenant_id).set_leader(
                    org_node_id, data.leader_id
                ),
            )
            return success(
                data=_serialize_org_node(org_node), message=_("role.leader_set")
            )

        register_tenant_recycle_bin_routes(
            router=router,
            service_class=TenantOrgNodeService,
            resource_name="organization",
        )


register_ai_switch_operation_permission(
    scope=PermissionScope.TENANT,
    resource="organization",
    action="manage_member_ai",
    name="action.organization.manage_member_ai",
    parent_resource="organization",
)

router = TenantOrganizationController.get_router()

__all__ = ["router", "TenantOrganizationController"]
