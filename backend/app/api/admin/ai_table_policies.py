"""
平台端 AI 表策略管理 API

提供 AI 表策略的查询和编辑接口（平台管理员专用）
策略由 sync 服务自动创建，管理员只做编辑和同步触发。
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, QueryParams, ActiveAdmin
from app.core.base_schema import PageResponse
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_update,
)
from app.schemas.ai.table_policy import (
    AITablePolicyUpdate,
    AITablePolicyResponse,
)
from app.services.ai.table_policy_service import AITablePolicyService


@permission_resource(
    resource="ai_table_policy",
    name="menu.admin.ai_table_policy",
    scope=PermissionScope.ADMIN,
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
    AI 表策略管理控制器

    提供策略查询、编辑、表同步接口
    """

    prefix = "/ai/table-policies"
    tags = [_("menu.tags.admin_ai_table_policy")]
    service_class = AITablePolicyService

    def _register_routes(self) -> None:
        """注册路由"""
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
            获取 AI 表策略列表

            - 支持通用筛选: filter[field][op]=value
            - 支持排序: sort=-created_at,table_name
            - 支持分页: page[number]=1&page[size]=20

            权限: ai_table_policy:list
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

        @router.get("/{policy_id}", summary="获取 AI 表策略详情")
        @action_read("action.ai_table_policy.detail")
        async def get_policy(
            request: Request,
            db: DbSession,
            policy_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取 AI 表策略详情

            权限: ai_table_policy:detail
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
            更新 AI 表策略配置

            权限: ai_table_policy:update
            """
            service = AITablePolicyService(db)
            policy = await service.get_or_raise(policy_id)

            update_data = data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(policy, key, value)

            await db.commit()
            await db.refresh(policy)

            # 清除 Redis schema 缓存（所有租户）
            from app.ai.data_intelligence.schema_provider import SchemaProvider
            await SchemaProvider.invalidate_cache(0)

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
            获取策略对应表的列信息

            用于 blocked_columns / readonly_columns 选择器

            权限: ai_table_policy:columns
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
            触发表策略同步（扫描新表并创建默认策略）

            权限: ai_table_policy:sync
            """
            from app.services.ai.table_policy_sync_service import sync_table_policies
            result = await sync_table_policies(db)

            # 清除 Redis schema 缓存
            from app.ai.data_intelligence.schema_provider import SchemaProvider
            await SchemaProvider.invalidate_cache(0)

            return success(
                data=result,
                message=_("common.success"),
            )


# 导出路由器
router = AdminAITablePolicyController.get_router()

__all__ = ["router", "AdminAITablePolicyController"]
