"""
任务管理 API

提供异步任务的查询、重试、取消等管理接口（平台管理员专用）
"""

from datetime import datetime, timedelta

from fastapi import Path, Query, Request

from app.core.base_controller import GlobalController
from app.core.deps import DbSession, QueryParams, ActiveAdmin
from app.core.i18n import _
from app.core.response import success, paginated
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_update,
)
from app.schemas.system import (
    TaskLogResponse,
    TaskLogDetailResponse,
    TaskStatsResponse,
    TaskRetryRequest,
    ActiveTaskResponse,
)
from app.services.system import TaskLogService, TaskManagerService


@permission_resource(
    resource="task_log",
    name="menu.admin.task_log",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:list-checks",
        path="/system/task-logs",
        component="admin/system/task-logs/index",
        parent="system_maintenance",
        sort_order=60,
    ),
)
class AdminTaskController(GlobalController):
    """
    任务管理控制器

    提供任务日志查询、统计、重试、取消等接口
    """

    prefix = "/tasks"
    tags = ["Task Management"]
    service_class = TaskLogService

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="获取任务日志列表")
        @action_read("action.task_log.list")
        async def list_tasks(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            query: QueryParams,
        ):
            service = self.get_service(db)
            items, total = await service.query_list(query)
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
            current_admin: ActiveAdmin,
            days: int = Query(7, ge=1, le=30, description="统计天数"),
        ):
            service = self.get_service(db)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            stats = await service.get_dashboard_stats(start_date, end_date)
            result = [
                TaskStatsResponse(
                    status=status,
                    count=data["count"],
                    avg_duration_ms=data["avg_duration_ms"],
                )
                for status, data in stats.items()
            ]
            return success(data=[item.model_dump() for item in result])

        @router.get("/active", summary="获取活跃任务")
        @action_read("action.task_log.active")
        async def active_tasks(
            request: Request,
            current_admin: ActiveAdmin,
        ):
            tasks = TaskManagerService.get_active_tasks()
            result = [ActiveTaskResponse(**t) for t in tasks]
            return success(data=[item.model_dump() for item in result])

        @router.get("/{task_log_id}", summary="获取任务详情")
        @action_read("action.task_log.detail")
        async def task_detail(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            task_log_id: int = Path(..., description="任务日志 ID"),
        ):
            service = self.get_service(db)
            task_log = await service.get_by_id(task_log_id)
            return success(
                data=TaskLogDetailResponse.model_validate(task_log, from_attributes=True).model_dump()
            )

        @router.post("/{task_log_id}/retry", summary="重试任务")
        @action_update("action.task_log.retry")
        async def retry_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            task_log_id: int = Path(..., description="任务日志 ID"),
            body: TaskRetryRequest | None = None,
        ):
            service = self.get_service(db)
            task_log = await service.get_by_id(task_log_id)
            new_task_id = TaskManagerService.retry_task(
                task_name=task_log.task_name,
                args=list(task_log.args.values()) if task_log.args else None,
                kwargs=task_log.kwargs,
                queue=body.queue if body and body.queue else task_log.queue,
            )
            return success(data={"new_task_id": new_task_id})

        @router.post("/{task_log_id}/cancel", summary="取消任务")
        @action_update("action.task_log.cancel")
        async def cancel_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            task_log_id: int = Path(..., description="任务日志 ID"),
        ):
            service = self.get_service(db)
            task_log = await service.get_by_id(task_log_id)
            TaskManagerService.cancel_task(task_log.task_id)
            return success(message=_("common.operation_success"))


router = AdminTaskController.get_router()
