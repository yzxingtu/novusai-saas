"""
租户端任务日志 API

提供租户端任务日志查询接口（只读，自动按 tenant_id 过滤）
"""

from datetime import timedelta

from fastapi import Query, Request

from app.core.base_controller import TenantController
from app.core.base_schema import PageResponse
from app.core.deps import DbSession, ActiveTenantAdmin, QueryParams
from app.core.i18n import _
from app.core.response import success, paginated
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
)
from app.schemas.system import (
    TaskLogResponse,
    TaskLogDetailResponse,
)
from app.services.tenant.task_log_service import TenantTaskLogService
from app.core.base_model import utc_now


@permission_resource(
    resource="task_log",
    name="menu.tenant.task_log",
    scope=PermissionScope.ALL_TENANTS,
    menu=MenuConfig(
        icon="lucide:list-checks",
        path="/system/task-logs",
        component="tenant/system/task-logs/index",
        parent="logs",
        sort_order=20,
    ),
)
class TenantTaskLogController(TenantController):
    """
    租户端任务日志控制器（只读）
    """

    prefix = "/tasks"
    tags = ["Task Log Management"]
    service_class = TenantTaskLogService

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="获取任务日志列表")
        @action_read("action.task_log.list")
        async def list_tasks(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            service = TenantTaskLogService(db, current_admin.tenant_id)
            items, total = await service.query_list(query, scope="tenant")
            return paginated(
                items=[TaskLogResponse.model_validate(item, from_attributes=True) for item in items],
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/stats", summary="获取任务统计")
        @action_read("action.task_log.stats")
        async def task_stats(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            days: int = Query(7, ge=1, le=30, description="统计天数"),
        ):
            service = TenantTaskLogService(db, current_admin.tenant_id)
            end_date = utc_now()
            start_date = end_date - timedelta(days=days)
            stats = await service.get_dashboard_stats(start_date, end_date)
            return success(data=stats, message=_("common.success"))

        @router.get("/{task_log_id}", summary="获取任务日志详情")
        @action_read("action.task_log.detail")
        async def get_task_log(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            task_log_id: int,
        ):
            service = TenantTaskLogService(db, current_admin.tenant_id)
            log = await service.get_by_id(task_log_id)
            if log is None:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("task_log.not_found"),
                )
            return success(
                data=TaskLogDetailResponse.model_validate(log, from_attributes=True),
                message=_("common.success"),
            )


router = TenantTaskLogController.get_router()

__all__ = ["router", "TenantTaskLogController"]
