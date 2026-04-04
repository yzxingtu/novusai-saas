"""
Execution decision API (admin) / 执行决策 API（管理端）

No standalone menu entry; the detail endpoint is consumed by action-logs'
linkedDecision card. / 无独立菜单入口；详情接口供 action-logs 关联决策卡片调用。
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    action_read,
    permission_resource,
)
from app.services.ai.execution_decision_service import AdminExecutionDecisionService


@permission_resource(
    resource="execution_decision",
    name="menu.admin.execution_decision",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_action_log",
)
class AdminExecutionDecisionController(GlobalController):
    prefix = "/ai/execution-decisions"
    tags = [_("menu.tags.admin_ai_action_audit")]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="获取执行决策列表")
        @action_read("action.execution_decision.list")
        async def list_execution_decisions(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            service = AdminExecutionDecisionService(db)
            items, total = await service.query_list(spec=spec)
            return paginated(
                items=await service.serialize_decisions(items),
                total=total,
                page=spec.page,
                page_size=spec.size,
            )

        @router.get("/{decision_id}", summary="获取执行决策详情")
        @action_read("action.execution_decision.detail")
        async def get_execution_decision_detail(
            request: Request,
            db: DbSession,
            decision_id: int,
            admin: ActiveAdmin,
        ):
            service = AdminExecutionDecisionService(db)
            item = await service.get_by_id(decision_id)
            if not item:
                raise NotFoundException(message=_("execution_decision.not_found"))
            return success(data=await service.serialize_decision(item))


router = AdminExecutionDecisionController.get_router()

__all__ = ["router", "AdminExecutionDecisionController"]
