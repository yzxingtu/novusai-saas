"""
任务管理 API / Task Management API

提供异步任务的查询、重试、取消等管理接口（平台管理员专用）
Provides async task query, retry, cancel and other management endpoints (platform admin only)
"""

from datetime import timedelta
from typing import Literal

from fastapi import Path, Query, Request
from sqlalchemy import select

from app.core.base_controller import GlobalController
from app.core.base_model import utc_now
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.models.system.task_definition import TaskDefinition
from app.models.tenant.tenant import Tenant
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.system import (
    ActiveTaskResponse,
    TaskLogDetailResponse,
    TaskLogResponse,
    TaskRetryRequest,
    TaskStatsResponse,
)
from app.services.system import TaskLogService, TaskManagerService


@permission_resource(
    resource="task_log",
    name="menu.admin.task_log",
    scope=PermissionScope.ADMIN,
    parent_resource="system_maintenance",
    menu=MenuConfig(
        icon="lucide:list-checks",
        path="/system/task-logs",
        component="admin/system/task-logs/index",
        parent="logs",
        sort_order=30,
    ),
)
class AdminTaskController(GlobalController):
    """
    任务管理控制器 / Task Management Controller

    提供任务日志查询、统计、重试、取消等接口
    Provides task log query, statistics, retry, cancel and other endpoints
    """

    prefix = "/tasks"
    tags = ["Task Management"]
    service_class = TaskLogService

    @staticmethod
    async def _build_relation_maps(db, task_runs) -> tuple[dict[int, dict[str, str]], dict[int, str]]:
        definition_ids = sorted(
            {
                task_run.task_definition_id
                for task_run in task_runs
                if task_run.task_definition_id is not None
            }
        )
        tenant_ids = sorted(
            {
                tenant_id
                for task_run in task_runs
                for tenant_id in (task_run.owner_tenant_id, task_run.effective_tenant_id)
                if tenant_id is not None
            }
        )
        definition_map: dict[int, dict[str, str]] = {}
        tenant_map: dict[int, str] = {}
        if definition_ids:
            result = await db.execute(
                select(TaskDefinition.id, TaskDefinition.name, TaskDefinition.scope).where(
                    TaskDefinition.id.in_(definition_ids)
                )
            )
            definition_map = {
                row.id: {"name": row.name, "scope": row.scope}
                for row in result.all()
            }
        if tenant_ids:
            result = await db.execute(select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_ids)))
            tenant_map = {row.id: row.name for row in result.all()}
        return definition_map, tenant_map

    @staticmethod
    def _serialize_task_run(
        task_run,
        *,
        definition_map: dict[int, dict[str, str]] | None = None,
        tenant_map: dict[int, str] | None = None,
    ) -> dict:
        args_summary = task_run.args_summary or {}
        args = None
        kwargs = None
        if isinstance(args_summary, dict):
            args = args_summary.get("args")
            kwargs = args_summary.get("kwargs")
        definition_info = (
            definition_map.get(task_run.task_definition_id, {})
            if definition_map and task_run.task_definition_id is not None
            else {}
        )
        owner_tenant_name = (
            tenant_map.get(task_run.owner_tenant_id)
            if tenant_map and task_run.owner_tenant_id is not None
            else None
        )
        effective_tenant_name = (
            tenant_map.get(task_run.effective_tenant_id)
            if tenant_map and task_run.effective_tenant_id is not None
            else None
        )

        return TaskLogResponse(
            id=task_run.id,
            task_id=task_run.celery_task_id,
            task_name=task_run.task_name_snapshot,
            handler_path=task_run.handler_path_snapshot,
            task_definition_id=task_run.task_definition_id,
            binding_id=task_run.binding_id,
            task_definition_name=definition_info.get("name"),
            task_scope=definition_info.get("scope"),
            owner_tenant_id=task_run.owner_tenant_id,
            owner_tenant_name=owner_tenant_name,
            effective_tenant_id=task_run.effective_tenant_id,
            effective_tenant_name=effective_tenant_name,
            queue=task_run.queue,
            status=task_run.status,
            args=args,
            kwargs=kwargs,
            result=task_run.result_summary,
            error_message=task_run.error_message_public
            or task_run.error_message_internal,
            trigger_source=task_run.trigger_source,
            run_kind=task_run.run_kind,
            trace_id=task_run.trace_id,
            started_at=task_run.started_at,
            finished_at=task_run.finished_at,
            duration_ms=task_run.duration_ms,
            retry_count=task_run.retry_count,
            tenant_id=task_run.effective_tenant_id,
            created_at=task_run.created_at,
        ).model_dump()

    @staticmethod
    def _serialize_task_run_detail(
        task_run,
        *,
        definition_map: dict[int, dict[str, str]] | None = None,
        tenant_map: dict[int, str] | None = None,
    ) -> dict:
        args_summary = task_run.args_summary or {}
        args = None
        kwargs = None
        if isinstance(args_summary, dict):
            args = args_summary.get("args")
            kwargs = args_summary.get("kwargs")
        definition_info = (
            definition_map.get(task_run.task_definition_id, {})
            if definition_map and task_run.task_definition_id is not None
            else {}
        )
        owner_tenant_name = (
            tenant_map.get(task_run.owner_tenant_id)
            if tenant_map and task_run.owner_tenant_id is not None
            else None
        )
        effective_tenant_name = (
            tenant_map.get(task_run.effective_tenant_id)
            if tenant_map and task_run.effective_tenant_id is not None
            else None
        )

        return TaskLogDetailResponse(
            id=task_run.id,
            task_id=task_run.celery_task_id,
            task_name=task_run.task_name_snapshot,
            handler_path=task_run.handler_path_snapshot,
            task_definition_id=task_run.task_definition_id,
            binding_id=task_run.binding_id,
            task_definition_name=definition_info.get("name"),
            task_scope=definition_info.get("scope"),
            owner_tenant_id=task_run.owner_tenant_id,
            owner_tenant_name=owner_tenant_name,
            effective_tenant_id=task_run.effective_tenant_id,
            effective_tenant_name=effective_tenant_name,
            queue=task_run.queue,
            status=task_run.status,
            args=args,
            kwargs=kwargs,
            result=task_run.result_summary,
            error_message=task_run.error_message_public
            or task_run.error_message_internal,
            trigger_source=task_run.trigger_source,
            run_kind=task_run.run_kind,
            trace_id=task_run.trace_id,
            started_at=task_run.started_at,
            finished_at=task_run.finished_at,
            duration_ms=task_run.duration_ms,
            retry_count=task_run.retry_count,
            tenant_id=task_run.effective_tenant_id,
            created_at=task_run.created_at,
            traceback=task_run.traceback_internal,
        ).model_dump()

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="获取任务日志列表")
        @action_read("action.task_log.list")
        async def list_tasks(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            query: QueryParams,
            view: Literal["all", "execution", "internal"] = Query(
                "all",
                description="Task log view mode",
            ),
        ):
            service = self.get_service(db)
            items, total = await service.query_list_by_view(query, view=view)
            definition_map, tenant_map = await self._build_relation_maps(db, items)
            return paginated(
                items=[
                    self._serialize_task_run(
                        item,
                        definition_map=definition_map,
                        tenant_map=tenant_map,
                    )
                    for item in items
                ],
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
            days: int = Query(7, ge=1, le=30, description=_("api.param.days")),
        ):
            service = self.get_service(db)
            end_date = utc_now()
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
            task_log_id: int = Path(..., description=_("api.param.task_log_id")),
        ):
            service = self.get_service(db)
            task_log = await service.get_by_id(task_log_id)
            if task_log is None:
                from app.exceptions import NotFoundException

                raise NotFoundException(message=_("task_log.error.not_found"))

            definition_map, tenant_map = await self._build_relation_maps(db, [task_log])
            return success(
                data=self._serialize_task_run_detail(
                    task_log,
                    definition_map=definition_map,
                    tenant_map=tenant_map,
                )
            )

        @router.post("/{task_log_id}/retry", summary="重试任务")
        @action_update("action.task_log.retry")
        async def retry_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            task_log_id: int = Path(..., description=_("api.param.task_log_id")),
            body: TaskRetryRequest | None = None,
        ):
            service = self.get_service(db)
            task_log = await service.get_by_id(task_log_id)
            if task_log is None:
                from app.exceptions import NotFoundException

                raise NotFoundException(message=_("task_log.error.not_found"))

            args_summary = task_log.args_summary or {}
            args = None
            kwargs = None
            if isinstance(args_summary, dict):
                args = args_summary.get("args")
                kwargs = args_summary.get("kwargs")

            new_task_id = TaskManagerService.retry_task(
                task_name=task_log.handler_path_snapshot,
                args=args if isinstance(args, list) else None,
                kwargs=kwargs if isinstance(kwargs, dict) else None,
                queue=body.queue if body and body.queue else task_log.queue,
            )
            return success(data={"new_task_id": new_task_id})

        @router.post("/{task_log_id}/cancel", summary="取消任务")
        @action_update("action.task_log.cancel")
        async def cancel_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            task_log_id: int = Path(..., description=_("api.param.task_log_id")),
        ):
            service = self.get_service(db)
            task_log = await service.get_by_id(task_log_id)
            if task_log is None:
                from app.exceptions import NotFoundException

                raise NotFoundException(message=_("task_log.error.not_found"))

            TaskManagerService.cancel_task(task_log.celery_task_id)
            return success(message=_("common.operation_success"))


router = AdminTaskController.get_router()
