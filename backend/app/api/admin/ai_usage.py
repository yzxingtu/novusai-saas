"""
AI 使用量统计管理 API (Admin) / AI Usage Statistics API (Admin)

提供平台级使用量统计查询接口（平台管理员专用）
Provides platform-level usage statistics query endpoints (platform admin only).
"""

from datetime import date

from fastapi import Query, Request

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    permission_resource,
)
from app.services.ai import MeteringService


@permission_resource(
    resource="ai_usage",
    name="menu.admin.ai_usage",
    scope=PermissionScope.ADMIN_ONLY,
    parent_resource="ai_quota_mgmt",
    menu=MenuConfig(
        icon="lucide:bar-chart-3",
        path="/ai/monitor/usage",
        component="ai/usage/index",
        parent="ai_ops",
        sort_order=20,
    ),
)
class AdminAIUsageController(GlobalController):
    """
    AI 使用量统计控制器 / AI Usage Statistics Controller

    提供平台级使用量统计查询接口 / Provides platform-level usage statistics query endpoints
    """

    prefix = "/ai/usage"
    tags = [_("menu.tags.admin_ai_usage")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("/summary/tenant/{tenant_id}", summary="获取企业使用量汇总")
        @action_read("action.ai_usage.tenant_summary")
        async def get_tenant_usage_summary(
            request: Request,
            db: DbSession,
            tenant_id: int,
            admin: ActiveAdmin,
            start_date: date | None = Query(None, description="开始日期"),
            end_date: date | None = Query(None, description="结束日期"),
        ):
            """
            获取指定企业的使用量汇总 / Get usage summary for specified tenant

            权限 / Permission: ai_usage:tenant_summary
            """
            metering = MeteringService(db)
            summary = await metering.get_tenant_usage(
                tenant_id=tenant_id,
                start_date=start_date,
                end_date=end_date,
            )

            return success(data=summary, message=_("common.success"))

        @router.get("/summary/model/{model_id}", summary="获取模型使用量汇总")
        @action_read("action.ai_usage.model_summary")
        async def get_model_usage_summary(
            request: Request,
            db: DbSession,
            model_id: int,
            admin: ActiveAdmin,
            start_date: date | None = Query(None, description="开始日期"),
            end_date: date | None = Query(None, description="结束日期"),
        ):
            """
            获取指定模型的使用量汇总 / Get usage summary for specified model

            权限 / Permission: ai_usage:model_summary
            """
            metering = MeteringService(db)
            summary = await metering.get_model_usage(
                model_id=model_id,
                start_date=start_date,
                end_date=end_date,
            )

            return success(data=summary, message=_("common.success"))

        @router.get("/stats", summary="查询使用量统计列表")
        @action_read("action.ai_usage.stats")
        async def list_usage_stats(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            """
            查询使用量统计列表 / Query usage statistics list

            支持 JSON:API 风格筛选和分页 / Supports JSON:API style filtering and pagination

            权限 / Permission: ai_usage:stats
            """
            from app.repositories.ai.usage_stat_repository import UsageStatRepository

            repo = UsageStatRepository(db)
            items, total = await repo.query_list_with_names(spec)

            return success(
                data=PageResponse.create(
                    items=items,
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )


# 导出路由器 / Export router
router = AdminAIUsageController.get_router()

__all__ = ["router", "AdminAIUsageController"]
