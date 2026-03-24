"""
AI 供应商健康状态 API (Admin) / AI Provider Health API (Admin)

提供供应商健康检查状态查询接口
Provides provider health check status query endpoints.
"""

from fastapi import Request
from sqlalchemy import select

from app.ai.failover import FailoverService
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.models.ai.provider import AIProvider
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    permission_resource,
)


@permission_resource(
    resource="ai_health",
    name="menu.admin.ai_health",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_infra",
    menu=MenuConfig(
        icon="lucide:heart-pulse",
        path="/ai/monitor/health",
        component="ai/health/index",
        parent="ai_infra",
        sort_order=40,
    ),
)
class AdminAIHealthController(GlobalController):
    """
    AI 供应商健康状态控制器 / AI Provider Health Status Controller

    提供供应商健康检查状态查询 / Provides provider health check status queries
    """

    prefix = "/ai/health"
    tags = [_("menu.tags.admin_ai_health")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("", summary="获取所有供应商健康状态")
        @action_read("action.ai_health.list")
        async def get_all_health(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取所有供应商当前健康状态（从 Redis 读取） / Get all provider current health status (from Redis)

            权限 / Permission: ai_health:list
            """
            statuses = await FailoverService.get_all_provider_health()

            # Enrich with provider icon / 补充供应商图标
            pid_set = {s.get("provider_id") for s in statuses if s.get("provider_id")}
            icon_map: dict[int, str | None] = {}
            if pid_set:
                rows = (await db.execute(
                    select(AIProvider.id, AIProvider.icon).where(AIProvider.id.in_(pid_set))
                )).all()
                icon_map = {r.id: r.icon for r in rows}
            for s in statuses:
                s["provider_icon"] = icon_map.get(s.get("provider_id"))

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
            获取供应商最近 24h 健康检查记录 / Get provider last 24h health check history

            权限 / Permission: ai_health:history
            """
            history = await FailoverService.get_provider_health_history(
                provider_id=provider_id,
                limit=288,  # 24h * 12 (every 5 min) / 24 小时 × 12 条（每 5 分钟采样）
            )
            return success(data=history, message=_("common.success"))


# 导出路由器 / Export router
router = AdminAIHealthController.get_router()

__all__ = ["router", "AdminAIHealthController"]
