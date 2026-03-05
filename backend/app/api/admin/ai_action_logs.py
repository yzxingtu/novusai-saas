"""
平台端 AI 操作审计日志 API

提供全局审计日志查询接口（只读）
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
from app.services.ai.action_log_service import AIActionLogService


@permission_resource(
    resource="ai_action_log",
    name="menu.admin.ai_action_log",
    scope=PermissionScope.ADMIN_ONLY,
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
    平台端 AI 操作审计日志控制器

    提供全局范围的审计日志查询
    """

    prefix = "/ai/action-logs"
    tags = [_("menu.tags.admin_ai_action_audit")]

    def _register_routes(self) -> None:
        """注册路由"""
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
            获取全局 AI 操作审计日志

            支持 JSON:API 筛选:
            - filter[tenant_id][eq]=1
            - filter[action_name][ilike]=xxx
            - filter[action_type][eq]=query/action/confirm
            - filter[status][eq]=success/failed/rejected
            - sort=-created_at

            权限: ai_action_log:list
            """
            # 使用 tenant_id=0 表示全局查询
            service = AIActionLogService(db, 0)
            items, total = await service.query_list(spec=spec)

            return paginated(
                items=[item.to_dict() for item in items],
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
            获取单条审计日志详情

            权限: ai_action_log:detail
            """
            service = AIActionLogService(db, 0)
            log = await service.get_by_id(log_id)

            if not log:
                raise NotFoundException(
                    message=_("ai_action_log.not_found"),
                )

            return success(data=log.to_dict())


# 导出路由器
router = AdminAIActionLogController.get_router()

__all__ = ["router", "AdminAIActionLogController"]
