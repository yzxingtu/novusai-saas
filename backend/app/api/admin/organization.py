"""
Platform organization APIs / 平台管理后台组织节点 API
"""

from __future__ import annotations

from fastapi import HTTPException, Query, Request, status

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.recycle_bin import register_admin_recycle_bin_routes
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException, NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.common import ReorderRequest
from app.schemas.system.admin_org_node import (
    AdminOrgNodeAssignMemberRequest,
    AdminOrgNodeAuthorityPolicyRequest,
    AdminOrgNodeCreateMemberRequest,
    AdminOrgNodeCreateRequest,
    AdminOrgNodeDetailResponse,
    AdminOrgNodeLeaderResponse,
    AdminOrgNodeMemberResponse,
    AdminOrgNodeMoveRequest,
    AdminOrgNodeResetPasswordRequest,
    AdminOrgNodeResponse,
    AdminOrgNodeSetLeaderRequest,
    AdminOrgNodeToggleStatusRequest,
    AdminOrgNodeUpdateMemberRequest,
    AdminOrgNodeUpdateRequest,
)
from app.services.system.admin_org_authority_service import AdminOrgAuthorityService
from app.services.system.admin_org_node_service import AdminOrgNodeService


def _serialize_leader(leader) -> AdminOrgNodeLeaderResponse | None:
    if not leader or getattr(leader, "is_deleted", False):
        return None
    return AdminOrgNodeLeaderResponse(
        id=leader.id,
        username=leader.username,
        nickname=leader.nickname,
        real_name=leader.nickname or leader.username,
        avatar=leader.avatar,
    )


def _serialize_org_node(org_node) -> AdminOrgNodeResponse:
    return AdminOrgNodeResponse(
        id=org_node.id,
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
        member_count=getattr(org_node, "member_count", 0),
        permissions_count=getattr(org_node, "permissions_count", 0),
        data_scope=getattr(org_node, "scope_mode", None) or "dept_children",
        custom_dept_ids=getattr(org_node, "custom_org_node_ids", None),
        created_at=org_node.created_at,
        updated_at=org_node.updated_at,
    )


def _serialize_org_node_detail(org_node) -> AdminOrgNodeDetailResponse:
    permissions = [
        permission
        for permission in getattr(org_node, "permissions", [])
        if permission.is_enabled and not permission.is_deleted
    ]
    return AdminOrgNodeDetailResponse(
        **_serialize_org_node(org_node).model_dump(),
        permission_ids=[permission.id for permission in permissions],
        permission_codes=[permission.code for permission in permissions],
    )


def _serialize_org_tree(org_nodes: list) -> list[dict]:
    if not org_nodes:
        return []

    node_map = {org_node.id: org_node for org_node in org_nodes}
    children_map: dict[int, list] = {org_node.id: [] for org_node in org_nodes}
    roots: list = []

    for org_node in org_nodes:
        if org_node.parent_id is not None and org_node.parent_id in node_map:
            children_map[org_node.parent_id].append(org_node)
        else:
            roots.append(org_node)

    def build(node) -> dict:
        payload = _serialize_org_node(node).model_dump()
        payload["children"] = [build(child) for child in children_map.get(node.id, [])]
        return payload

    return [build(root) for root in roots]


def _serialize_member(member) -> AdminOrgNodeMemberResponse:
    org_relation = getattr(member, "org_node", None)
    is_leader = (
        org_relation is not None
        and getattr(org_relation, "leader_id", None) == member.id
    )
    return AdminOrgNodeMemberResponse(
        id=member.id,
        username=member.username,
        nickname=member.nickname,
        avatar=member.avatar,
        email=member.email,
        is_active=member.is_active,
        is_leader=is_leader,
        joined_at=member.created_at,
        org_node_id=getattr(member, "org_node_id", None),
        org_node_name=getattr(org_relation, "name", None),
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


def _raise_http(exc: Exception):
    if isinstance(exc, NotFoundException):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.message)
        )
    if isinstance(exc, BusinessException):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc.message)
        )
    raise exc


@permission_resource(
    resource="organization",
    name="menu.admin.organization",
    scope=PermissionScope.ADMIN,
    parent_resource="platform_mgmt",
    menu=MenuConfig(
        icon="lucide:git-branch",
        path="/system/organization",
        component="admin/system/organization/index",
        parent="system",
        sort_order=15,
    ),
)
class AdminOrganizationController(GlobalController):
    """Platform organization controller / 平台组织节点控制器"""

    prefix = "/organization"
    tags = ["Organization Management (Platform)"]

    async def _require_view(
        self, db: DbSession, admin: ActiveAdmin, org_node_id: int
    ) -> None:
        if not await AdminOrgAuthorityService(db, admin).can_view_org_node(org_node_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_("role.no_permission_to_view"),
            )

    async def _require_manage(
        self, db: DbSession, admin: ActiveAdmin, org_node_id: int
    ) -> None:
        if not await AdminOrgAuthorityService(db, admin).can_manage_org_node(
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
            request: Request, db: DbSession, current_admin: ActiveAdmin
        ):
            service = AdminOrgNodeService(db)
            authority = AdminOrgAuthorityService(db, current_admin)
            if current_admin.is_super:
                return success(
                    data=_serialize_org_tree(await service.get_visible_org_tree()),
                    message=_("common.success"),
                )

            scope_ids = await authority.get_visible_org_node_ids()
            return success(
                data=_serialize_org_tree(await service.get_visible_org_tree(scope_ids)),
                message=_("common.success"),
            )

        @router.get("", summary="获取组织根节点")
        @action_read("action.organization.organization")
        async def get_org_roots(
            request: Request, db: DbSession, current_admin: ActiveAdmin
        ):
            service = AdminOrgNodeService(db)
            authority = AdminOrgAuthorityService(db, current_admin)
            if current_admin.is_super:
                nodes = await service.get_visible_root_nodes()
                return success(
                    data=[_serialize_org_node(node) for node in nodes],
                    message=_("common.success"),
                )

            scope_ids = await authority.get_visible_org_node_ids()
            items = await service.get_visible_root_nodes(scope_ids)
            return success(data=items, message=_("common.success"))

        @router.put("/reorder", summary="批量重排序组织节点")
        @action_update("action.organization.reorder")
        async def reorder_org_nodes(
            request: Request,
            db: DbSession,
            data: ReorderRequest,
            current_admin: ActiveAdmin,
        ):
            authority = AdminOrgAuthorityService(db, current_admin)
            if not current_admin.is_super:
                for org_node_id in data.ids:
                    if not await authority.can_manage_org_node(org_node_id):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=_("role.no_permission_to_manage"),
                        )
            updated_count = await AdminOrgNodeService(db).reorder(
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
            current_admin: ActiveAdmin,
        ):
            await self._require_view(db, current_admin, org_node_id)
            org_node = await AdminOrgNodeService(db).get_org_node_detail(org_node_id)
            return success(
                data=_serialize_org_node_detail(org_node), message=_("common.success")
            )

        @router.get("/{org_node_id}/children", summary="获取组织子节点")
        @action_read("action.organization.children")
        async def get_org_children(
            request: Request,
            db: DbSession,
            org_node_id: int,
            current_admin: ActiveAdmin,
        ):
            await self._require_view(db, current_admin, org_node_id)
            nodes = await AdminOrgNodeService(db).get_organization_children(org_node_id)
            return success(
                data=[_serialize_org_node(node) for node in nodes],
                message=_("common.success"),
            )

        @router.post("", summary="创建组织节点")
        @action_create("action.organization.create")
        async def create_org_node(
            request: Request,
            db: DbSession,
            data: AdminOrgNodeCreateRequest,
            current_admin: ActiveAdmin,
        ):
            if not await AdminOrgAuthorityService(
                db, current_admin
            ).can_create_under_parent(data.parent_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.parent_must_be_visible"),
                )
            try:
                org_node = await AdminOrgNodeService(db).create_org_node(
                    **data.model_dump()
                )
                await db.commit()
                return success(
                    data=_serialize_org_node(org_node), message=_("role.created")
                )
            except Exception as exc:
                _raise_http(exc)

        @router.put("/{org_node_id}", summary="更新组织节点")
        @action_update("action.organization.update")
        async def update_org_node(
            request: Request,
            db: DbSession,
            org_node_id: int,
            data: AdminOrgNodeUpdateRequest,
            current_admin: ActiveAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            if data.parent_id is not None and not await AdminOrgAuthorityService(
                db, current_admin
            ).can_create_under_parent(data.parent_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.parent_must_be_visible"),
                )
            try:
                org_node = await AdminOrgNodeService(db).update_org_node(
                    org_node_id,
                    data.model_dump(exclude_unset=True),
                )
                await db.commit()
                return success(
                    data=_serialize_org_node(org_node), message=_("role.updated")
                )
            except Exception as exc:
                _raise_http(exc)

        @router.put("/{org_node_id}/move", summary="移动组织节点")
        @action_update("action.organization.move")
        async def move_org_node(
            request: Request,
            db: DbSession,
            org_node_id: int,
            data: AdminOrgNodeMoveRequest,
            current_admin: ActiveAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            if data.new_parent_id is not None and not await AdminOrgAuthorityService(
                db, current_admin
            ).can_create_under_parent(data.new_parent_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_("role.parent_must_be_visible"),
                )
            try:
                org_node = await AdminOrgNodeService(db).move_org_node(
                    org_node_id,
                    data.new_parent_id,
                )
                await db.commit()
                return success(
                    data=_serialize_org_node(org_node), message=_("role.moved")
                )
            except Exception as exc:
                _raise_http(exc)

        @router.put("/{org_node_id}/authority", summary="更新组织权限范围策略")
        @action_update("action.organization.update_authority")
        async def update_org_authority(
            request: Request,
            db: DbSession,
            org_node_id: int,
            data: AdminOrgNodeAuthorityPolicyRequest,
            current_admin: ActiveAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            try:
                org_node = await AdminOrgNodeService(db).update_authority_policy(
                    org_node_id,
                    data_scope=data.data_scope,
                    custom_dept_ids=data.custom_dept_ids,
                )
                await db.commit()
                return success(
                    data=_serialize_org_node(org_node), message=_("role.updated")
                )
            except Exception as exc:
                _raise_http(exc)

        @router.delete("/{org_node_id}", summary="删除组织节点")
        @action_delete("action.organization.delete")
        async def delete_org_node(
            request: Request,
            db: DbSession,
            org_node_id: int,
            current_admin: ActiveAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            try:
                await AdminOrgNodeService(db).delete_org_node(org_node_id)
                await db.commit()
                return success(data={"id": org_node_id}, message=_("role.deleted"))
            except Exception as exc:
                _raise_http(exc)

        @router.get("/{org_node_id}/members", summary="获取组织节点成员")
        @action_read("action.organization.members")
        async def get_org_members(
            request: Request,
            db: DbSession,
            org_node_id: int,
            current_admin: ActiveAdmin,
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
            try:
                members, total = await AdminOrgNodeService(db).get_members(
                    org_node_id,
                    search=search or None,
                    page=page,
                    page_size=page_size,
                    include_descendants=include_descendants,
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
            except Exception as exc:
                _raise_http(exc)

        @router.post("/{org_node_id}/members/create", summary="在组织节点下创建成员")
        @action_create("action.organization.create_member")
        async def create_member(
            request: Request,
            db: DbSession,
            org_node_id: int,
            data: AdminOrgNodeCreateMemberRequest,
            current_admin: ActiveAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            try:
                admin = await AdminOrgNodeService(db).create_member(
                    org_node_id=org_node_id,
                    username=data.username,
                    email=data.email,
                    password=data.password,
                    phone=data.phone,
                    nickname=data.nickname,
                    is_active=data.is_active,
                )
                await db.commit()
                return success(
                    data=_serialize_member(admin), message=_("role.member_created")
                )
            except Exception as exc:
                _raise_http(exc)

        @router.put("/{org_node_id}/members/{admin_id}", summary="更新组织节点成员")
        @action_update("action.organization.update_member")
        async def update_member(
            request: Request,
            db: DbSession,
            org_node_id: int,
            admin_id: int,
            data: AdminOrgNodeUpdateMemberRequest,
            current_admin: ActiveAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            if data.org_node_id is not None:
                await self._require_manage(db, current_admin, data.org_node_id)
            try:
                admin = await AdminOrgNodeService(db).update_member(
                    org_node_id=org_node_id,
                    admin_id=admin_id,
                    email=data.email,
                    phone=data.phone,
                    nickname=data.nickname,
                    avatar=data.avatar,
                    is_active=data.is_active,
                    new_org_node_id=data.org_node_id,
                )
                await db.commit()
                return success(
                    data=_serialize_member(admin), message=_("role.member_updated")
                )
            except Exception as exc:
                _raise_http(exc)

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
            data: AdminOrgNodeResetPasswordRequest,
            current_admin: ActiveAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            try:
                await AdminOrgNodeService(db).reset_member_password(
                    org_node_id,
                    admin_id,
                    data.new_password,
                )
                await db.commit()
                return success(
                    data={"success": True}, message=_("admin.password_reset")
                )
            except Exception as exc:
                _raise_http(exc)

        @router.put(
            "/{org_node_id}/members/{admin_id}/status", summary="切换组织节点成员状态"
        )
        @action_update("action.organization.toggle_status")
        async def toggle_member_status(
            request: Request,
            db: DbSession,
            org_node_id: int,
            admin_id: int,
            data: AdminOrgNodeToggleStatusRequest,
            current_admin: ActiveAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            try:
                admin = await AdminOrgNodeService(db).toggle_member_status(
                    org_node_id,
                    admin_id,
                    data.is_active,
                )
                await db.commit()
                return success(
                    data=_serialize_member(admin), message=_("admin.status_updated")
                )
            except Exception as exc:
                _raise_http(exc)

        @router.post("/{org_node_id}/members", summary="分配成员到组织节点")
        @action_update("action.organization.assign_member")
        async def assign_member(
            request: Request,
            db: DbSession,
            org_node_id: int,
            data: AdminOrgNodeAssignMemberRequest,
            current_admin: ActiveAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            try:
                admin = await AdminOrgNodeService(db).add_member(
                    org_node_id, data.admin_id
                )
                await db.commit()
                return success(
                    data=_serialize_member(admin), message=_("role.member_added")
                )
            except Exception as exc:
                _raise_http(exc)

        @router.delete(
            "/{org_node_id}/members/{admin_id}", summary="从组织节点移除成员"
        )
        @action_update("action.organization.remove_member")
        async def remove_member(
            request: Request,
            db: DbSession,
            org_node_id: int,
            admin_id: int,
            current_admin: ActiveAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            try:
                admin = await AdminOrgNodeService(db).remove_member(
                    org_node_id, admin_id
                )
                await db.commit()
                return success(
                    data=_serialize_member(admin), message=_("role.member_removed")
                )
            except Exception as exc:
                _raise_http(exc)

        @router.put("/{org_node_id}/leader", summary="设置组织节点负责人")
        @action_update("action.organization.set_leader")
        async def set_leader(
            request: Request,
            db: DbSession,
            org_node_id: int,
            data: AdminOrgNodeSetLeaderRequest,
            current_admin: ActiveAdmin,
        ):
            await self._require_manage(db, current_admin, org_node_id)
            try:
                org_node = await AdminOrgNodeService(db).set_leader(
                    org_node_id, data.leader_id
                )
                await db.commit()
                return success(
                    data=_serialize_org_node(org_node), message=_("role.leader_set")
                )
            except Exception as exc:
                _raise_http(exc)

        register_admin_recycle_bin_routes(
            router=router,
            service_class=AdminOrgNodeService,
            resource_name="organization",
        )


router = AdminOrganizationController.get_router()

__all__ = ["router", "AdminOrganizationController"]
