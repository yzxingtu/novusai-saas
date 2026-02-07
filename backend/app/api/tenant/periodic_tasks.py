"""
租户端定时任务管理 API

提供租户端定时任务 CRUD、启停、手动触发接口（自动按 tenant_id 过滤）
"""

from fastapi import Request

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
    action_create,
    action_update,
    action_delete,
)
from app.schemas.system import (
    PeriodicTaskResponse,
    PeriodicTaskCreateRequest,
    PeriodicTaskUpdateRequest,
)
from app.services.tenant.periodic_task_service import TenantPeriodicTaskService


@permission_resource(
    resource="periodic_task",
    name="menu.tenant.periodic_task",
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:timer",
        path="/system/periodic-tasks",
        component="tenant/system/periodic-tasks/index",
        parent="system_maintenance",
        sort_order=61,
    ),
)
class TenantPeriodicTaskController(TenantController):
    """
    租户端定时任务控制器
    """

    prefix = "/periodic-tasks"
    tags = ["定时任务管理"]
    service_class = TenantPeriodicTaskService

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="获取定时任务列表")
        @action_read("action.periodic_task.list")
        async def list_periodic_tasks(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            service = TenantPeriodicTaskService(db, current_admin.tenant_id)
            items, total = await service.query_list(query, scope="tenant")
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
            current_admin: ActiveTenantAdmin,
            body: PeriodicTaskCreateRequest,
        ):
            service = TenantPeriodicTaskService(db, current_admin.tenant_id)
            task = await service.create(body.model_dump(exclude_unset=True))
            await db.commit()
            await db.refresh(task)
            return success(
                data=PeriodicTaskResponse.model_validate(task, from_attributes=True),
                message=_("common.created"),
            )

        @router.get("/{task_id}", summary="获取定时任务详情")
        @action_read("action.periodic_task.detail")
        async def get_periodic_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            task_id: int,
        ):
            service = TenantPeriodicTaskService(db, current_admin.tenant_id)
            task = await service.get_by_id(task_id)
            if task is None:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=_("periodic_task.not_found"),
                )
            return success(
                data=PeriodicTaskResponse.model_validate(task, from_attributes=True),
                message=_("common.success"),
            )

        @router.put("/{task_id}", summary="更新定时任务")
        @action_update("action.periodic_task.update")
        async def update_periodic_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            task_id: int,
            body: PeriodicTaskUpdateRequest,
        ):
            service = TenantPeriodicTaskService(db, current_admin.tenant_id)
            task = await service.update(task_id, body.model_dump(exclude_unset=True))
            await db.commit()
            await db.refresh(task)
            return success(
                data=PeriodicTaskResponse.model_validate(task, from_attributes=True),
                message=_("common.updated"),
            )

        @router.delete("/{task_id}", summary="删除定时任务")
        @action_delete("action.periodic_task.delete")
        async def delete_periodic_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            task_id: int,
        ):
            service = TenantPeriodicTaskService(db, current_admin.tenant_id)
            await service.delete(task_id)
            await db.commit()
            return success(message=_("common.deleted"))

        @router.post("/{task_id}/toggle", summary="启用/禁用定时任务")
        @action_update("action.periodic_task.toggle")
        async def toggle_periodic_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            task_id: int,
            body: dict,
        ):
            service = TenantPeriodicTaskService(db, current_admin.tenant_id)
            task = await service.toggle_active(task_id, body.get("is_active", False))
            await db.commit()
            await db.refresh(task)
            return success(
                data=PeriodicTaskResponse.model_validate(task, from_attributes=True),
                message=_("common.updated"),
            )

        @router.post("/{task_id}/trigger", summary="手动触发定时任务")
        @action_update("action.periodic_task.trigger")
        async def trigger_periodic_task(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            task_id: int,
        ):
            service = TenantPeriodicTaskService(db, current_admin.tenant_id)
            triggered_task_id = await service.trigger_now(task_id)
            return success(
                data={"triggered_task_id": triggered_task_id},
                message=_("common.success"),
            )


router = TenantPeriodicTaskController.get_router()

__all__ = ["router", "TenantPeriodicTaskController"]
