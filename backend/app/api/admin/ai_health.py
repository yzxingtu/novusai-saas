"""
AI 供应商健康状态 API (Admin)

提供供应商健康检查状态查询接口
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
)
from app.ai.failover import FailoverService


@permission_resource(
    resource="ai_health",
    name="menu.admin.ai_health",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:heart-pulse",
        path="/ai/monitor/health",
        component="ai/health/index",
        parent="ai_infra",
        sort_order=30,
    ),
)
class AdminAIHealthController(GlobalController):
    """
    AI 供应商健康状态控制器

    提供供应商健康检查状态查询
    """

    prefix = "/ai/health"
    tags = [_("menu.tags.admin_ai_health")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="获取所有供应商健康状态")
        @action_read("action.ai_health.list")
        async def get_all_health(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取所有供应商当前健康状态（从 Redis 读取）

            权限: ai_health:list
            """
            statuses = await FailoverService.get_all_provider_health()
            return success(data=statuses, message=_("common.success"))

        @router.get("/{provider_id}/history", summary="获取供应商健康检查历史")
        @action_read("action.ai_health.history")
        async def get_health_history(
            request: Request,
            db: DbSession,
            provider_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取供应商最近 24h 健康检查记录

            权限: ai_health:history
            """
            history = await FailoverService.get_provider_health_history(
                provider_id=provider_id,
                limit=288,  # 24h * 12 (every 5 min)
            )
            return success(data=history, message=_("common.success"))


# 导出路由器
router = AdminAIHealthController.get_router()

__all__ = ["router", "AdminAIHealthController"]
