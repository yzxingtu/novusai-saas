"""
AI 操作审计日志管理 API (Admin) / AI Action Log API (Admin)
提供全局审计日志查询接口（只读） / Provides global audit log query endpoints (read-only)
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    permission_resource,
)
from app.services.ai.action_log_service import AdminAIActionLogService


@permission_resource(
    resource="ai_action_log",
    name="menu.admin.ai_action_log",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_quota_mgmt",
    menu=MenuConfig(
        icon="lucide:shield-check",
        path="/ai/action-logs",
        component="admin/ai/action-logs/index",
        parent="ai_ops",
        sort_order=30,
    ),
)
class AdminAIActionLogController(GlobalController):
    """
    平台端 AI 操作审计日志控制器 / Platform AI Action Audit Log Controller

    提供全局范围的审计日志查询 / Provides global scope audit log queries
    """

    prefix = "/ai/action-logs"
    tags = [_("menu.tags.admin_ai_action_audit")]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("", summary="获取全局审计日志列表")
        @action_read("action.ai_action_log.list")
        async def list_action_logs(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            """
            获取全局 AI 操作审计日志 / Get global AI action audit logs

            支持 JSON:API 筛选 / Supports JSON:API filtering:
            - filter[tenant_id][eq]=1
            - filter[action_name][ilike]=xxx
            - filter[action_type][eq]=query/action/confirm
            - filter[status][eq]=success/failed/rejected
            - sort=-created_at

            权限 / Permission: ai_action_log:list
            """
            service = AdminAIActionLogService(db)
            items, total = await service.query_list(spec=spec)

            return paginated(
                items=await service.serialize_logs(items),
                total=total,
                page=spec.page,
                page_size=spec.size,
            )

        @router.get("/{log_id}", summary="获取审计日志详情")
        @action_read("action.ai_action_log.detail")
        async def get_action_log_detail(
            request: Request,
            db: DbSession,
            log_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取单条审计日志详情 / Get single audit log details

            权限 / Permission: ai_action_log:detail
            """
            service = AdminAIActionLogService(db)
            log = await service.get_by_id(log_id)

            if not log:
                raise NotFoundException(
                    message=_("ai_action_log.not_found"),
                )

            return success(data=await service.serialize_log(log))


# 导出路由器 / Export router
router = AdminAIActionLogController.get_router()

__all__ = ["router", "AdminAIActionLogController"]
