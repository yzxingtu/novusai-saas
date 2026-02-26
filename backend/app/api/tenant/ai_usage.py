"""
AI 使用量统计 API (Tenant)

提供租户级使用量统计查询接口
"""

from datetime import date
from typing import Optional

from fastapi import Query, Request

from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin
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
    resource="ai_tenant_usage",
    name="menu.tenant.ai_usage",
    scope=PermissionScope.ALL_TENANTS,
    menu=MenuConfig(
        icon="lucide:bar-chart-3",
        path="/ai/usage",
        component="ai/usage/index",
        parent="ai_analytics",
        sort_order=30,
    ),
)
class TenantAIUsageController(TenantController):
    """
    租户 AI 使用量控制器

    提供租户级使用量统计查询
    """

    prefix = "/ai/usage"
    tags = [_("menu.tags.tenant_ai_usage")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("/summary", summary="获取当前租户使用量汇总")
        @action_read("action.ai_tenant_usage.summary")
        async def get_tenant_usage_summary(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            start_date: Optional[date] = Query(None, description="开始日期"),
            end_date: Optional[date] = Query(None, description="结束日期"),
        ):
            """
            获取当前租户使用量汇总

            权限: ai_tenant_usage:summary
            """
            metering = MeteringService(db)
            summary = await metering.get_tenant_usage(
                tenant_id=tenant_admin.tenant_id,
                start_date=start_date,
                end_date=end_date,
            )

            return success(data=summary, message=_("common.success"))

        @router.get("/summary/user/{user_id}", summary="获取用户使用量汇总")
        @action_read("action.ai_tenant_usage.user_summary")
        async def get_user_usage_summary(
            request: Request,
            db: DbSession,
            user_id: int,
            tenant_admin: ActiveTenantAdmin,
            start_date: Optional[date] = Query(None, description="开始日期"),
            end_date: Optional[date] = Query(None, description="结束日期"),
        ):
            """
            获取租户下指定用户的使用量汇总

            权限: ai_tenant_usage:user_summary
            """
            metering = MeteringService(db)
            summary = await metering.get_user_usage(
                tenant_id=tenant_admin.tenant_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )

            return success(data=summary, message=_("common.success"))


# 导出路由器
router = TenantAIUsageController.get_router()

__all__ = ["router", "TenantAIUsageController"]
