"""
AI 使用量统计管理 API (Admin)

提供平台级使用量统计查询接口（平台管理员专用）
"""

from datetime import date
from typing import Optional

from fastapi import Query, Request

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
)
from app.services.ai import MeteringService


@permission_resource(
    resource="ai_usage",
    name="menu.admin.ai_usage",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:bar-chart-3",
        path="/ai/monitor/usage",
        component="ai/usage/index",
        parent="ai_monitor",
        sort_order=20,
    ),
)
class AdminAIUsageController(GlobalController):
    """
    AI 使用量统计控制器

    提供平台级使用量统计查询接口
    """

    prefix = "/ai/usage"
    tags = ["AI 使用量统计"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("/summary/tenant/{tenant_id}", summary="获取租户使用量汇总")
        @action_read("action.ai_usage.tenant_summary")
        async def get_tenant_usage_summary(
            request: Request,
            db: DbSession,
            tenant_id: int,
            admin: ActiveAdmin,
            start_date: Optional[date] = Query(None, description="开始日期"),
            end_date: Optional[date] = Query(None, description="结束日期"),
        ):
            """
            获取指定租户的使用量汇总

            权限: ai_usage:tenant_summary
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
            start_date: Optional[date] = Query(None, description="开始日期"),
            end_date: Optional[date] = Query(None, description="结束日期"),
        ):
            """
            获取指定模型的使用量汇总

            权限: ai_usage:model_summary
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
            查询使用量统计列表

            支持 JSON:API 风格筛选和分页

            权限: ai_usage:stats
            """
            from app.repositories.ai.usage_stat_repository import UsageStatRepository

            repo = UsageStatRepository(db)
            items, total = await repo.query_list(spec)

            return success(
                data=PageResponse.create(
                    items=items,
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )


# 导出路由器
router = AdminAIUsageController.get_router()

__all__ = ["router", "AdminAIUsageController"]
