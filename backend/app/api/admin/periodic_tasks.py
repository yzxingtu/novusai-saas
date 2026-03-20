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
    PeriodicTaskCreateRequest,
    PeriodicTaskResponse,
    PeriodicTaskToggleRequest,
    PeriodicTaskUpdateRequest,
)
from app.services.system import PeriodicTaskService


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
    service_class = PeriodicTaskService

    def _register_routes(self) -> None:
        router = self.router

        # 回收站路由必须在 /{task_id} 之前注册，避免路径冲突 / Recycle bin routes must be registered before /{task_id} to avoid path conflicts
        register_admin_recycle_bin_routes(
            router=router,
            service_class=PeriodicTaskService,
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
                if item.next_run_at is None and item.is_active:
                    next_run = PeriodicTaskService._compute_next_run(item)
                    if next_run:
                        item.next_run_at = next_run
            return paginated(
                items=[PeriodicTaskResponse.model_validate(item, from_attributes=True) for item in items],
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
            task = await service.create(body.model_dump(exclude_unset=True))
            return created(
                data=PeriodicTaskResponse.model_validate(task, from_attributes=True).model_dump()
            )

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

            return success(
                data=PeriodicTaskResponse.model_validate(task, from_attributes=True).model_dump()
            )

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
            task = await service.update(task_id, body.model_dump(exclude_unset=True))
            return success(
                data=PeriodicTaskResponse.model_validate(task, from_attributes=True).model_dump()
            )

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
            return success(
                data=PeriodicTaskResponse.model_validate(task, from_attributes=True).model_dump()
            )

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
