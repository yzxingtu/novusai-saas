"""
套餐管理 API / Plan Management API

提供企业套餐 CRUD 接口（平台管理员专用）
Provides tenant plan CRUD endpoints (platform admin only).
"""

from fastapi import Query, Request

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.recycle_bin import register_admin_recycle_bin_routes
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.common import ReorderRequest
from app.schemas.tenant.plan import (
    PermissionSimpleResponse,
    PermissionTreeSimpleResponse,
    TenantPlanCreateRequest,
    TenantPlanDetailResponse,
    TenantPlanPermissionsRequest,
    TenantPlanResponse,
    TenantPlanUpdateRequest,
)
from app.services.tenant import TenantPlanService


def _translate_permission_name(name: str) -> str:
    """
    翻译权限名称 / Translate permission name

    Args:
        name: 权限名称（可能是 i18n key） / Permission name (may be i18n key)

    Returns:
        翻译后的名称 / Translated name
    """
    if name and "." in name:
        translated = _(name)
        if translated == name:
            return name.split(".")[-1]
        return translated
    return name or ""


@permission_resource(
    resource="tenant_plan",
    name="menu.admin.tenant_plan",  # i18n key
    scope=PermissionScope.ADMIN,
    parent_resource="platform_mgmt",
    menu=MenuConfig(
        icon="lucide:package",
        path="/tenant/plans",
        component="tenant/Plans",
        parent="tenant_mgmt",  # 父菜单: 企业管理 / Parent menu: Tenant Management
        sort_order=20,
    ),
)
class AdminPlanController(GlobalController):
    """
    套餐管理控制器 / Plan Management Controller

    提供套餐 CRUD、权限分配等接口 / Provides plan CRUD, permission assignment endpoints
    """

    prefix = "/plans"
    tags = ["Plan Management"]
    service_class = TenantPlanService

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        # 回收站路由必须在 /{id} 之前注册，避免路径冲突 / Recycle bin routes must be registered before /{id} to avoid path conflicts
        register_admin_recycle_bin_routes(
            router=router,
            service_class=TenantPlanService,
            resource_name="tenant_plan",
        )

        @router.get("/select", summary="获取套餐下拉选项")
        @action_read("action.tenant_plan.select")
        async def select_plans(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            search: str = Query("", description=_("api.param.search")),
            is_active: str = Query("true", description=_("api.param.is_active")),
            page: int = Query(0, ge=0, description=_("api.param.page")),
            page_size: int = Query(20, ge=1, le=100, description=_("api.param.page_size")),
        ):
            """
            获取套餐下拉选项 / Get plan dropdown options

            用于筛选器或表单中的套餐选择组件 / Used for plan selection component in filters or forms

            分页模式 / Pagination mode:
            - page=0: 不分页，返回全部数据（受 limit 限制） / No pagination, return all data (limited by limit)
            - page>=1: 分页模式，返回分页信息（total, has_more） / Paginated mode, returns pagination info

            权限 / Permission: tenant_plan:select
            """
            service = TenantPlanService(db)

            # 解析 is_active 参数 / Parse is_active parameter
            active_filter: bool | None = True
            if is_active.lower() == "false":
                active_filter = False
            elif is_active.lower() == "all" or is_active == "":
                active_filter = None

            # 根据是否筛选状态获取选项 / Get options based on status filter
            if active_filter is not None:
                response = await service.get_select_options(
                    search=search,
                    limit=50,
                    is_active=active_filter,
                    page=page,
                    page_size=page_size,
                )
            else:
                response = await service.get_select_options(
                    search=search,
                    limit=50,
                    page=page,
                    page_size=page_size,
                )

            return success(
                data=response,
                message=_("common.success"),
            )

        @router.get("", summary="获取套餐列表")
        @action_read("action.tenant_plan.list")
        async def list_plans(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            current_admin: ActiveAdmin,
        ):
            """
            获取所有套餐列表 / Get all plan list

            - 支持通用筛选 / Supports generic filter: filter[field][op]=value
            - 支持排序 / Supports sorting: sort=-created_at,name
            - 支持分页 / Supports pagination: page[number]=1&page[size]=20

            权限 / Permission: tenant_plan:list
            """
            service = TenantPlanService(db)
            items, total = await service.query_list(spec, scope="admin")

            # 批量获取企业数量（高效 COUNT 查询，避免加载全部企业对象） / Batch get tenant counts (efficient COUNT query, avoids loading all tenant objects)
            plan_ids = [item.id for item in items]
            tenant_counts = await service.repo.get_tenant_counts_batch(plan_ids)
            for item in items:
                item.tenants_count = tenant_counts.get(item.id, 0)

            return success(
                data=PageResponse.create(
                    items=[TenantPlanResponse.from_model(item) for item in items],
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        @router.get("/available-permissions", summary="获取可分配的权限树")
        @action_read("action.tenant_plan.available_permissions")
        async def get_available_permissions(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            获取可分配给套餐的权限树 / Get assignable permission tree for plans

            返回 tenant/both scope 的 menu 类型权限（树形结构） / Returns menu-type permissions with tenant/both scope (tree structure)

            权限 / Permission: tenant_plan:available_permissions
            """
            service = TenantPlanService(db)
            permissions = await service.get_available_permissions()

            # 构建权限树 / Build permission tree
            def build_tree(
                perms: list,
                parent_id: int | None = None
            ) -> list[PermissionTreeSimpleResponse]:
                """递归构建权限树 / Recursively build permission tree"""
                tree = []
                for p in perms:
                    if p.parent_id == parent_id:
                        children = build_tree(perms, p.id)
                        tree.append(PermissionTreeSimpleResponse(
                            id=p.id,
                            code=p.code,
                            name=_translate_permission_name(p.name),
                            type=p.type,
                            resource=p.resource,
                            parent_id=p.parent_id,
                            sort_order=p.sort_order,
                            children=children,
                        ))
                return sorted(tree, key=lambda x: x.sort_order)

            return success(
                data=build_tree(permissions),
                message=_("common.success"),
            )

        @router.get("/{plan_id}", summary="获取套餐详情")
        @action_read("action.tenant_plan.detail")
        async def get_plan(
            request: Request,
            db: DbSession,
            plan_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            获取套餐详情（含权限列表） / Get plan detail (with permission list)

            权限 / Permission: tenant_plan:detail
            """
            service = TenantPlanService(db)
            plan = await service.get_with_permissions(plan_id)

            if plan is None:
                raise NotFoundException(
                    message=_("tenant_plan.not_found"),
                )

            return success(
                data=TenantPlanDetailResponse.from_model(plan, translate_fn=_translate_permission_name),
                message=_("common.success"),
            )

        @router.post("", summary="创建套餐")
        @action_create("action.tenant_plan.create")
        async def create_plan(
            request: Request,
            db: DbSession,
            data: TenantPlanCreateRequest,
            current_admin: ActiveAdmin,
        ):
            """
            创建套餐 / Create plan

            - code: 套餐代码（唯一） / Plan code (unique)
            - name: 套餐名称 / Plan name
            - price: 价格 / Price
            - billing_cycle: 计费周期 / Billing cycle
            - quota: 配额配置 / Quota config
            - features: 特性标记 / Feature flags

            权限 / Permission: tenant_plan:create
            """
            service = TenantPlanService(db)
            plan = await service.create_plan(data)
            await db.commit()

            return success(
                data=TenantPlanResponse.from_model(plan),
                message=_("tenant_plan.created"),
            )

        # ========== 排序管理 API / Sort Management API ==========
        # 注意：/reorder 必须放在 /{plan_id} 之前，否则会被路径参数匹配 / Note: /reorder must be before /{plan_id} to avoid path param matching

        @router.put("/reorder", summary="批量重排序")
        @action_update("action.tenant_plan.reorder")
        async def reorder_plans(
            request: Request,
            db: DbSession,
            data: ReorderRequest,
            current_admin: ActiveAdmin,
        ):
            """
            批量重排序套餐 / Batch reorder plans

            接收有序的 ID 列表，按顺序重新分配排序值。
            Receives ordered ID list, reassigns sort values in order.

            请求示例 / Request example:
                {
                    "ids": [3, 1, 5, 2, 4]
                }

            权限 / Permission: tenant_plan:reorder
            """
            service = TenantPlanService(db)

            try:
                updated_count = await service.reorder(ordered_ids=data.ids)
                await db.commit()

                return success(
                    data={"updated_count": updated_count},
                    message=_("common.reorder_success"),
                )

            except ValueError as e:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )

        @router.put("/{plan_id}", summary="更新套餐")
        @action_update("action.tenant_plan.update")
        async def update_plan(
            request: Request,
            db: DbSession,
            plan_id: int,
            data: TenantPlanUpdateRequest,
            current_admin: ActiveAdmin,
        ):
            """
            更新套餐 / Update plan

            权限 / Permission: tenant_plan:update
            """
            service = TenantPlanService(db)
            plan = await service.update_plan(plan_id, data)
            await db.commit()

            return success(
                data=TenantPlanResponse.from_model(plan),
                message=_("tenant_plan.updated"),
            )

        @router.delete("/{plan_id}", summary="删除套餐")
        @action_delete("action.tenant_plan.delete")
        async def delete_plan(
            request: Request,
            db: DbSession,
            plan_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            删除套餐（软删除） / Delete plan (soft delete)

            - 如果有企业正在使用该套餐，则无法删除 / Cannot delete if tenants are using this plan

            权限 / Permission: tenant_plan:delete
            """
            service = TenantPlanService(db)
            await service.delete_plan(plan_id)
            await db.commit()

            return success(
                message=_("tenant_plan.deleted"),
            )

        @router.get("/{plan_id}/permissions", summary="获取套餐权限")
        @action_read("action.tenant_plan.permissions")
        async def get_plan_permissions(
            request: Request,
            db: DbSession,
            plan_id: int,
            current_admin: ActiveAdmin,
        ):
            """
            获取套餐关联的权限列表 / Get plan associated permission list

            权限 / Permission: tenant_plan:permissions
            """
            service = TenantPlanService(db)
            permissions = await service.get_plan_permissions(plan_id)

            return success(
                data=[
                    PermissionSimpleResponse(
                        id=p.id,
                        code=p.code,
                        name=_translate_permission_name(p.name),
                        type=p.type,
                        resource=p.resource,
                    )
                    for p in permissions
                    if p.is_enabled
                ],
                message=_("common.success"),
            )

        @router.put("/{plan_id}/permissions", summary="设置套餐权限")
        @action_update("action.tenant_plan.assign_permissions")
        async def assign_plan_permissions(
            request: Request,
            db: DbSession,
            plan_id: int,
            data: TenantPlanPermissionsRequest,
            current_admin: ActiveAdmin,
        ):
            """
            设置套餐关联的权限 / Set plan associated permissions

            - 仅支持 tenant/both scope 的 menu 类型权限 / Only supports menu-type permissions with tenant/both scope
            - 无效的权限 ID 会被自动过滤 / Invalid permission IDs are auto-filtered

            权限 / Permission: tenant_plan:assign_permissions
            """
            service = TenantPlanService(db)
            plan = await service.assign_permissions(plan_id, data.permission_ids)
            await db.commit()

            return success(
                data=TenantPlanDetailResponse.from_model(plan, translate_fn=_translate_permission_name),
                message=_("tenant_plan.permissions_updated"),
            )



# 导出路由器 / Export router
router = AdminPlanController.get_router()


__all__ = ["router", "AdminPlanController"]
