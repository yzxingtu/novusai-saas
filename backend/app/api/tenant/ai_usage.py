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
from app.services.ai.monitoring_service import MonitoringService


@permission_resource(
    resource="ai_tenant_usage",
    name="menu.tenant.ai_usage",
    scope=PermissionScope.TENANT,
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

        @router.get("/dashboard", summary="获取企业监控仪表盘")
        @action_read("action.ai_tenant_usage.summary")
        async def get_tenant_usage_dashboard(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            start_date: date | None = Query(None, description=_("api.param.start_date")),
            end_date: date | None = Query(None, description=_("api.param.end_date")),
        ):
            _request = request
            monitoring = MonitoringService(db)
            dashboard = await monitoring.get_usage_dashboard(
                monitoring.tenant_scope(tenant_admin.tenant_id),
                start_date=start_date,
                end_date=end_date,
            )
            return success(data=dashboard, message=_("common.success"))


# 导出路由器 / Export router
router = TenantAIUsageController.get_router()

__all__ = ["router", "TenantAIUsageController"]
