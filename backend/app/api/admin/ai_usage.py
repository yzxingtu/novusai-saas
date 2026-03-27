"""
AI 使用量统计管理 API (Admin) / AI Usage Statistics API (Admin)

提供平台级使用量统计查询接口（平台管理员专用）
Provides platform-level usage statistics query endpoints (platform admin only).
"""

from datetime import date

from fastapi import Query, Request

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
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
    resource="ai_usage",
    name="menu.admin.ai_usage",
    scope=PermissionScope.ADMIN,
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

        @router.get("/dashboard", summary="获取监控仪表盘")
        @action_read("action.ai_usage.stats")
        async def get_usage_dashboard(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            start_date: date | None = Query(None, description="开始日期"),
            end_date: date | None = Query(None, description="结束日期"),
        ):
            _request = request
            _admin = admin
            monitoring = MonitoringService(db)
            dashboard = await monitoring.get_usage_dashboard(
                monitoring.admin_scope(),
                start_date=start_date,
                end_date=end_date,
            )
            return success(data=dashboard, message=_("common.success"))


# 导出路由器 / Export router
router = AdminAIUsageController.get_router()

__all__ = ["router", "AdminAIUsageController"]
