"""
租户端 AI 操作审计日志 API

提供审计日志列表、详情和统计接口（只读）
"""

from fastapi import Request

from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    permission_resource,
)
from app.services.ai.action_log_service import AIActionLogService


@permission_resource(
    resource="ai_action_log",
    name="menu.tenant.ai_action_log",
    scope=PermissionScope.ALL_TENANTS,
    menu=MenuConfig(
        icon="lucide:shield-check",
        path="/ai/action-logs",
        component="tenant/ai/action-logs/index",
        parent="ai_analytics",
        sort_order=50,
    ),
)
class TenantAIActionLogController(TenantController):
    """
    租户 AI 操作审计日志控制器

    提供只读的审计日志查询和统计接口
    """

    prefix = "/ai/action-logs"
    tags = [_("menu.tags.tenant_ai_action_audit")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="获取审计日志列表")
        @action_read("action.ai_action_log.list")
        async def list_action_logs(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取当前租户的 AI 操作审计日志

            支持 JSON:API 筛选:
            - filter[action_name][ilike]=xxx
            - filter[action_type][eq]=query/action/confirm
            - filter[action_level][eq]=read/safe_write/dangerous
            - filter[status][eq]=success/failed/rejected
            - filter[created_at][gte]=2026-01-01
            - sort=-created_at

            权限: ai_action_log:list
            """
            service = AIActionLogService(db, tenant_admin.tenant_id)
            items, total = await service.query_list(spec=spec)

            return paginated(
                items=[item.to_dict() for item in items],
                total=total,
                page=spec.page,
                page_size=spec.size,
            )

        @router.get("/stats", summary="获取审计统计信息")
        @action_read("action.ai_action_log.stats")
        async def get_action_log_stats(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取审计日志统计信息

            返回: 总数、各状态计数、各级别计数、平均耗时

            权限: ai_action_log:stats
            """
            service = AIActionLogService(db, tenant_admin.tenant_id)
            stats = await service.get_stats()
            distribution = await service.get_type_distribution()

            return success(data={
                "stats": stats,
                "type_distribution": distribution,
            })

        @router.get("/{log_id}", summary="获取审计日志详情")
        @action_read("action.ai_action_log.detail")
        async def get_action_log_detail(
            request: Request,
            db: DbSession,
            log_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取单条审计日志详情

            权限: ai_action_log:detail
            """
            service = AIActionLogService(db, tenant_admin.tenant_id)
            log = await service.get_by_id(log_id)

            if not log:
                raise NotFoundException(
                    message=_("ai_action_log.not_found"),
                )

            return success(data=log.to_dict())


# 导出路由器
router = TenantAIActionLogController.get_router()

__all__ = ["router", "TenantAIActionLogController"]
