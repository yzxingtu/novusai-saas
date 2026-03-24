"""
定时任务管理 API / Periodic Task API

提供定时任务的 CRUD、启用/禁用、手动触发等管理接口
Provides periodic task CRUD, enable/disable, manual trigger endpoints.
"""

from fastapi import Path, Request

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.recycle_bin import register_admin_recycle_bin_routes
from app.core.response import created, deleted, paginated, success
from app.enums.rbac import PermissionScope
from app.rbac.decorators import (
    MenuConfig,
    action_create,
    action_delete,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.system import (
    PeriodicTaskBindingResponse,
    PeriodicTaskBindingSyncRequest,
    PeriodicTaskCreateRequest,
    PeriodicTaskResponse,
    PeriodicTaskToggleRequest,
    PeriodicTaskUpdateRequest,
)
from app.services.system import TaskBindingService, TaskDefinitionService


@permission_resource(
    resource="periodic_task",
    name="menu.admin.periodic_task",
    scope=PermissionScope.ADMIN,
    parent_resource="system_maintenance",
    menu=MenuConfig(
        icon="lucide:timer",
        path="/system/periodic-tasks",
        component="admin/system/periodic-tasks/index",
        parent="system_maintenance",
        sort_order=50,
    ),
)
class AdminPeriodicTaskController(GlobalController):
    """
    定时任务管理控制器 / Periodic Task Management Controller
    """

    prefix = "/periodic-tasks"
    tags = ["Periodic Task Management"]
    service_class = TaskDefinitionService

    @staticmethod
    def _serialize_definition(definition) -> dict:
        return PeriodicTaskResponse(
            id=definition.id,
            name=definition.name,
            task_path=definition.handler_path,
            schedule_type=definition.default_schedule_type,
            cron_expression=definition.default_cron_expression,
            interval_seconds=definition.default_interval_seconds,
            is_active=definition.is_enabled,
            last_run_at=definition.last_run_at,
            next_run_at=definition.next_run_at,
            description=definition.description,
            scope=definition.scope,
            owner_tenant_id=definition.owner_tenant_id,
            is_locked=not definition.is_deletable,
            is_editable=definition.is_editable,
            max_retries=definition.max_retries,
            retry_delay=definition.retry_delay,
            timeout=definition.timeout,
            notify_on_failure=definition.notify_on_failure,
            notify_emails=definition.notify_emails,
            created_at=definition.created_at,
        ).model_dump()

    def _register_routes(self) -> None:
        router = self.router

        # 回收站路由必须在 /{task_id} 之前注册，避免路径冲突 / Recycle bin routes must be registered before /{task_id} to avoid path conflicts
        register_admin_recycle_bin_routes(
            router=router,
            service_class=TaskDefinitionService,
            resource_name="periodic_task",
        )

        @router.get("", summary="获取定时任务列表")
        @action_read("action.periodic_task.list")
        async def list_periodic_tasks(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            query: QueryParams,
        ):
            service = self.get_service(db)
            items, total = await service.query_list(query)
            # Fill next_run_at when null for Cron/Interval tasks (e.g. pre-seeded tasks)
            # 当 next_run_at 为空时，为 Cron/Interval 任务计算下次执行时间
            for item in items:
                if item.next_run_at is None and item.is_enabled:
                    next_run = TaskDefinitionService._compute_next_run(
                        item.default_schedule_type,
                        item.default_cron_expression,
                        item.default_interval_seconds,
                    )
                    if next_run:
                        item.next_run_at = next_run
            return paginated(
                items=[self._serialize_definition(item) for item in items],
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.post("", summary="创建定时任务")
        @action_create("action.periodic_task.create")
        async def create_periodic_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: PeriodicTaskCreateRequest,
        ):
            service = self.get_service(db)
            payload = {
                "name": body.name,
                "handler_path": body.task_path,
                "default_schedule_type": body.schedule_type,
                "default_cron_expression": body.cron_expression,
                "default_interval_seconds": body.interval_seconds,
                "default_args": body.args,
                "default_kwargs": body.kwargs,
                "description": body.description,
                "scope": body.scope,
                "owner_tenant_id": body.owner_tenant_id,
                "is_enabled": body.is_active,
                "is_editable": body.is_editable,
                "is_deletable": not body.is_locked,
                "max_retries": body.max_retries,
                "retry_delay": body.retry_delay,
                "timeout": body.timeout,
                "notify_on_failure": body.notify_on_failure,
                "notify_emails": body.notify_emails,
                "default_queue": "scheduled",
                "definition_type": "system",
            }
            task = await service.create(payload)
            return created(data=self._serialize_definition(task))

        @router.get("/{task_id}", summary="获取定时任务详情")
        @action_read("action.periodic_task.detail")
        async def get_periodic_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            task_id: int = Path(..., description=_("api.param.task_id")),
        ):
            service = self.get_service(db)
            task = await service.get_by_id(task_id)
            if task is None:
                from app.exceptions import NotFoundException
                raise NotFoundException(message=_("periodic_task.error.not_found"))

            return success(data=self._serialize_definition(task))

        @router.get("/{task_id}/bindings", summary="获取定时任务企业绑定")
        @action_read("action.periodic_task.bindings")
        async def list_periodic_task_bindings(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            task_id: int = Path(..., description=_("api.param.task_id")),
        ):
            _ = (request, current_admin)
            service = self.get_service(db)
            task = await service.get_by_id(task_id)
            if task is None:
                from app.exceptions import NotFoundException

                raise NotFoundException(message=_("periodic_task.error.not_found"))

            binding_service = TaskBindingService(db)
            items = await binding_service.list_by_definition(task_id)
            return success(
                data=[
                    PeriodicTaskBindingResponse(**item).model_dump()
                    for item in items
                ]
            )

        @router.put("/{task_id}/bindings", summary="同步定时任务企业绑定")
        @action_update("action.periodic_task.bindings")
        async def sync_periodic_task_bindings(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: PeriodicTaskBindingSyncRequest,
            task_id: int = Path(..., description=_("api.param.task_id")),
        ):
            _ = (request, current_admin)
            service = self.get_service(db)
            task = await service.get_by_id(task_id)
            if task is None:
                from app.exceptions import NotFoundException

                raise NotFoundException(message=_("periodic_task.error.not_found"))

            binding_service = TaskBindingService(db)
            result = await binding_service.sync_definition_bindings(
                task_id,
                body.tenant_ids,
            )
            await db.commit()
            return success(data=result)

        @router.put("/{task_id}", summary="更新定时任务")
        @action_update("action.periodic_task.update")
        async def update_periodic_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: PeriodicTaskUpdateRequest,
            task_id: int = Path(..., description=_("api.param.task_id")),
        ):
            service = self.get_service(db)
            raw = body.model_dump(exclude_unset=True)
            payload = {}
            field_map = {
                "name": "name",
                "task_path": "handler_path",
                "schedule_type": "default_schedule_type",
                "cron_expression": "default_cron_expression",
                "interval_seconds": "default_interval_seconds",
                "args": "default_args",
                "kwargs": "default_kwargs",
                "description": "description",
                "scope": "scope",
                "owner_tenant_id": "owner_tenant_id",
                "is_active": "is_enabled",
                "is_editable": "is_editable",
                "max_retries": "max_retries",
                "retry_delay": "retry_delay",
                "timeout": "timeout",
                "notify_on_failure": "notify_on_failure",
                "notify_emails": "notify_emails",
            }
            for old_key, new_key in field_map.items():
                if old_key in raw:
                    payload[new_key] = raw[old_key]
            if "is_locked" in raw:
                payload["is_deletable"] = not raw["is_locked"]
            task = await service.update(task_id, payload)
            return success(data=self._serialize_definition(task))

        @router.delete("/{task_id}", summary="删除定时任务")
        @action_delete("action.periodic_task.delete")
        async def delete_periodic_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            task_id: int = Path(..., description=_("api.param.task_id")),
        ):
            service = self.get_service(db)
            await service.delete(task_id)
            return deleted()

        @router.post("/{task_id}/toggle", summary="启用/禁用定时任务")
        @action_update("action.periodic_task.toggle")
        async def toggle_periodic_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            body: PeriodicTaskToggleRequest,
            task_id: int = Path(..., description=_("api.param.task_id")),
        ):
            service = self.get_service(db)
            task = await service.toggle_active(task_id, body.is_active)
            return success(data=self._serialize_definition(task))

        @router.post("/{task_id}/trigger", summary="手动触发定时任务")
        @action_update("action.periodic_task.trigger")
        async def trigger_periodic_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
            task_id: int = Path(..., description=_("api.param.task_id")),
        ):
            service = self.get_service(db)
            new_task_id = await service.trigger_now(task_id)
            return success(data={"triggered_task_id": new_task_id})


router = AdminPeriodicTaskController.get_router()
