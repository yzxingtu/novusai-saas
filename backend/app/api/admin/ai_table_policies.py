"""
平台端 AI 表策略管理 API / Platform AI Table Policy API

提供 AI 表策略的查询和编辑接口（平台管理员专用）
Provides AI table policy query and edit endpoints (platform admin only).
策略由 sync 服务自动创建，管理员只做编辑和同步触发。
Policies are auto-created by sync service; admins only edit and trigger sync.
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.ai.table_policy import (
    AITablePolicyResponse,
    AITablePolicyUpdate,
)
from app.services.ai.table_policy_service import AITablePolicyService


@permission_resource(
    resource="ai_table_policy",
    name="menu.admin.ai_table_policy",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_infra",
    menu=MenuConfig(
        icon="lucide:shield-check",
        path="/ai/table-policies",
        component="ai/table-policies/index",
        parent="ai_infra",
        sort_order=25,
    ),
)
class AdminAITablePolicyController(GlobalController):
    """
    AI 表策略管理控制器 / AI Table Policy Management Controller

    提供策略查询、编辑、表同步接口 / Provides policy query, edit, and table sync endpoints
    """

    prefix = "/ai/table-policies"
    tags = [_("menu.tags.admin_ai_table_policy")]
    service_class = AITablePolicyService

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("", summary="获取 AI 表策略列表")
        @action_read("action.ai_table_policy.list")
        async def list_policies(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            """
            获取 AI 表策略列表 / Get AI table policy list

            - 支持通用筛选 / General filtering: filter[field][op]=value
            - 支持排序 / Sorting: sort=-created_at,table_name
            - 支持分页 / Pagination: page[number]=1&page[size]=20

            权限 / Permission: ai_table_policy:list
            """
            service = AITablePolicyService(db)
            items, total = await service.query_list(spec)

            return success(
                data=PageResponse.create(
                    items=[
                        AITablePolicyResponse.model_validate(item, from_attributes=True)
                        for item in items
                    ],
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        @router.get("/declared-tables", summary="获取声明了 __ai_policy__ 的表名列表")
        @action_read("action.ai_table_policy.list")
        async def get_declared_tables(
            request: Request,
            admin: ActiveAdmin,
        ):
            """
            获取声明了 __ai_policy__ 的表名列表 / Get table names with __ai_policy__ declaration

            用于前端标记未声明的历史策略 / For frontend to mark undeclared legacy policies

            权限 / Permission: ai_table_policy:list
            """
            from app.services.ai.table_policy_sync_service import (
                get_declared_table_names,
            )

            names = list(get_declared_table_names())
            return success(
                data=names,
                message=_("common.success"),
            )

        @router.get("/{policy_id}", summary="获取 AI 表策略详情")
        @action_read("action.ai_table_policy.detail")
        async def get_policy(
            request: Request,
            db: DbSession,
            policy_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取 AI 表策略详情 / Get AI table policy details

            权限 / Permission: ai_table_policy:detail
            """
            service = AITablePolicyService(db)
            policy = await service.get_or_raise(policy_id)

            return success(
                data=AITablePolicyResponse.model_validate(policy, from_attributes=True),
                message=_("common.success"),
            )

        @router.put("/{policy_id}", summary="更新 AI 表策略")
        @action_update("action.ai_table_policy.update")
        async def update_policy(
            request: Request,
            db: DbSession,
            policy_id: int,
            data: AITablePolicyUpdate,
            admin: ActiveAdmin,
        ):
            """
            更新 AI 表策略配置 / Update AI table policy config

            权限 / Permission: ai_table_policy:update
            """
            service = AITablePolicyService(db)
            policy = await service.get_or_raise(policy_id)

            update_data = data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(policy, key, value)

            await db.commit()
            await db.refresh(policy)

            # 清除所有企业 schema 缓存（平台策略变更影响全租户）/ Clear all tenant schema caches
            from app.ai.data_intelligence.schema_provider import SchemaProvider

            await SchemaProvider.invalidate_all_schema_caches()

            return success(
                data=AITablePolicyResponse.model_validate(policy, from_attributes=True),
                message=_("common.success"),
            )

        @router.get("/{policy_id}/columns", summary="获取表的列信息")
        @action_read("action.ai_table_policy.columns")
        async def get_table_columns(
            request: Request,
            db: DbSession,
            policy_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取策略对应表的列信息 / Get column info for the policy's table

            用于 blocked_columns / readonly_columns 选择器 / Used for blocked_columns / readonly_columns selectors

            权限 / Permission: ai_table_policy:columns
            """
            service = AITablePolicyService(db)
            columns = await service.get_table_columns(policy_id)

            return success(
                data=columns,
                message=_("common.success"),
            )

        @router.post("/sync", summary="触发表策略同步")
        @action_update("action.ai_table_policy.sync")
        async def sync_policies(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            触发表策略同步（扫描新表并创建默认策略） / Trigger table policy sync (scan new tables and create default policies)

            权限 / Permission: ai_table_policy:sync
            """
            from app.services.ai.table_policy_sync_service import sync_table_policies

            result = await sync_table_policies(db)

            # 清除所有企业 schema 缓存（同步后影响全租户）/ Clear all tenant schema caches
            from app.ai.data_intelligence.schema_provider import SchemaProvider

            await SchemaProvider.invalidate_all_schema_caches()

            return success(
                data=result,
                message=_("common.success"),
            )


# 导出路由器 / Export router
router = AdminAITablePolicyController.get_router()

__all__ = ["router", "AdminAITablePolicyController"]
