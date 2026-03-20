"""
AI 使用量统计 API (Tenant) / AI Usage Statistics API (Tenant)

提供企业级使用量统计查询接口
Provides tenant-level usage statistics query endpoints
"""

from datetime import date

from fastapi import Query, Request

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    permission_resource,
)
from app.repositories.ai import AICallLogRepository


@permission_resource(
    resource="ai_tenant_usage",
    name="menu.tenant.ai_usage",
    scope=PermissionScope.ALL_TENANTS,
    parent_resource="ai_analytics",
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
    企业 AI 使用量控制器 / Tenant AI Usage Controller

    提供企业级使用量统计查询
    Provides tenant-level usage statistics query
    """

    prefix = "/ai/usage"
    tags = [_("menu.tags.tenant_ai_usage")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("/summary", summary="获取当前企业使用量汇总")
        @action_read("action.ai_tenant_usage.summary")
        async def get_tenant_usage_summary(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            start_date: date | None = Query(None, description=_("api.param.start_date")),
            end_date: date | None = Query(None, description=_("api.param.end_date")),
        ):
            """
            获取当前企业使用量汇总 / Get current tenant usage summary

            权限 / Permission: ai_tenant_usage:summary
            """
            repo = AICallLogRepository(db)
            summary = await repo.get_billing_tenant_usage_summary(
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
            start_date: date | None = Query(None, description=_("api.param.start_date")),
            end_date: date | None = Query(None, description=_("api.param.end_date")),
        ):
            """
            获取企业下指定用户的使用量汇总 / Get usage summary for specified user under tenant

            权限 / Permission: ai_tenant_usage:user_summary
            """
            repo = AICallLogRepository(db)
            summary = await repo.get_billing_user_usage_summary(
                tenant_id=tenant_admin.tenant_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )

            return success(data=summary, message=_("common.success"))


# 导出路由器 / Export router
router = TenantAIUsageController.get_router()

__all__ = ["router", "TenantAIUsageController"]
