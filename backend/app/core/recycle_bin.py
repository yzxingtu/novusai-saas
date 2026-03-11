"""
回收站路由注册工具 / Recycle Bin Route Registration Utility

为 Controller 提供标准化的回收站 API 端点注册。
Provides standardized recycle bin API endpoint registration for Controllers.

使用示例（TenantController）:
    from app.core.recycle_bin import register_tenant_recycle_bin_routes

    class TenantAgentController(TenantController):
        def _register_routes(self) -> None:
            # ... 其他路由 ...
            register_tenant_recycle_bin_routes(
                router=self.router,
                service_class=AgentService,
                resource_name="agent",
            )

使用示例（GlobalController）:
    from app.core.recycle_bin import register_admin_recycle_bin_routes

    class AdminAgentController(GlobalController):
        def _register_routes(self) -> None:
            # ... 其他路由 ...
            register_admin_recycle_bin_routes(
                router=self.router,
                service_class=AgentService,
                resource_name="agent",
            )
"""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Request

from app.core.deps import ActiveAdmin, ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.response import deleted, paginated, success
from app.enums.common import DeleteLevelEnum
from app.exceptions import NotFoundException, ValidationException
from app.rbac.decorators import action_delete

_MAX_BATCH_SIZE = 100


def register_tenant_recycle_bin_routes(
    router: APIRouter,
    service_class: type,
    resource_name: str,
    serialize: Callable | None = None,
) -> None:
    """
    为租户端控制器注册回收站路由
    Register recycle bin routes for tenant-side controllers.

    租户端回收站行为：
    Tenant-side recycle bin behavior:
    - 查询：查 delete_level='tenant' 的记录 / Query: records with delete_level='tenant'
    - 恢复：还原记录 / Restore: undelete records
    - 删除：升级到 admin 回收站（escalate_delete） / Delete: escalate to admin recycle bin

    Args:
        router: 控制器路由器 / Controller router
        service_class: 服务类（TenantService 子类） / Service class (TenantService subclass)
        resource_name: 资源名称（用于 i18n） / Resource name (for i18n)
        serialize: 可选的序列化函数，将 ORM 实例转为 dict / Optional serializer, converts ORM instance to dict
    """
    _serialize = serialize or _default_serialize

    @router.get("/recycle-bin/count", summary="回收站计数")
    @action_delete(f"action.{resource_name}.recycle_bin")
    async def recycle_bin_count(
        request: Request,
        db: DbSession,
        tenant_admin: ActiveTenantAdmin,
    ):
        svc = service_class(db, tenant_admin.tenant_id)
        count = await svc.count_deleted(delete_level=DeleteLevelEnum.TENANT.value)
        return success(data={"count": count})

    @router.get("/recycle-bin", summary="回收站列表")
    @action_delete(f"action.{resource_name}.recycle_bin")
    async def recycle_bin_list(
        request: Request,
        db: DbSession,
        tenant_admin: ActiveTenantAdmin,
        query: QueryParams,
    ):
        svc = service_class(db, tenant_admin.tenant_id)
        items, total = await svc.query_deleted_list(
            spec=query,
            delete_level=DeleteLevelEnum.TENANT.value,
        )
        result = [_serialize_with_delete_meta(item, _serialize) for item in items]
        return paginated(
            items=result,
            total=total,
            page=query.page,
            page_size=query.size,
        )

    @router.post("/recycle-bin/{item_id}/restore", summary="恢复记录")
    @action_delete(f"action.{resource_name}.recycle_bin")
    async def recycle_bin_restore(
        request: Request,
        db: DbSession,
        item_id: int,
        tenant_admin: ActiveTenantAdmin,
    ):
        svc = service_class(db, tenant_admin.tenant_id)
        instance = await svc.restore(item_id)
        if not instance:
            raise NotFoundException(message=_("recycle_bin.error.not_found"))
        await db.commit()
        return success(message=_("recycle_bin.restored"))

    @router.delete("/recycle-bin/{item_id}", summary="从回收站删除（升级到管理端）")
    @action_delete(f"action.{resource_name}.recycle_bin")
    async def recycle_bin_delete(
        request: Request,
        db: DbSession,
        item_id: int,
        tenant_admin: ActiveTenantAdmin,
    ):
        svc = service_class(db, tenant_admin.tenant_id)
        instance = await svc.escalate_delete(item_id)
        if not instance:
            raise NotFoundException(message=_("recycle_bin.error.not_found"))
        await db.commit()
        return success(message=_("recycle_bin.escalated"))

    @router.post("/recycle-bin/batch-restore", summary="批量恢复")
    @action_delete(f"action.{resource_name}.recycle_bin")
    async def recycle_bin_batch_restore(
        request: Request,
        db: DbSession,
        tenant_admin: ActiveTenantAdmin,
        ids: list[int] = Body(..., embed=True),
    ):
        if len(ids) > _MAX_BATCH_SIZE:
            raise ValidationException(message=_("recycle_bin.error.batch_too_large"))
        svc = service_class(db, tenant_admin.tenant_id)
        count = await svc.batch_restore(ids)
        await db.commit()
        return success(data={"count": count}, message=_("recycle_bin.restored"))

    @router.delete("/recycle-bin/batch", summary="批量删除（升级到管理端）")
    @action_delete(f"action.{resource_name}.recycle_bin")
    async def recycle_bin_batch_delete(
        request: Request,
        db: DbSession,
        tenant_admin: ActiveTenantAdmin,
        ids: list[int] = Body(..., embed=True),
    ):
        if len(ids) > _MAX_BATCH_SIZE:
            raise ValidationException(message=_("recycle_bin.error.batch_too_large"))
        svc = service_class(db, tenant_admin.tenant_id)
        # 逐个升级，因为 batch_permanent_delete 是物理删除 / Escalate one by one since batch_permanent_delete is hard delete
        count = 0
        for item_id in ids:
            result = await svc.escalate_delete(item_id)
            if result:
                count += 1
        await db.commit()
        return success(data={"count": count}, message=_("recycle_bin.escalated"))


def register_admin_recycle_bin_routes(
    router: APIRouter,
    service_class: type,
    resource_name: str,
    serialize: Callable | None = None,
) -> None:
    """
    为管理端控制器注册回收站路由
    Register recycle bin routes for admin-side controllers.

    管理端回收站行为：
    Admin-side recycle bin behavior:
    - 查询：查 delete_level='admin' 的记录 / Query: records with delete_level='admin'
    - 恢复：还原记录 / Restore: undelete records
    - 删除：物理删除（permanent_delete） / Delete: permanent hard delete

    Args:
        router: 控制器路由器 / Controller router
        service_class: 服务类（GlobalService/BaseService 子类） / Service class (GlobalService/BaseService subclass)
        resource_name: 资源名称（用于 i18n） / Resource name (for i18n)
        serialize: 可选的序列化函数 / Optional serializer
    """
    _serialize = serialize or _default_serialize

    @router.get("/recycle-bin/count", summary="回收站计数")
    @action_delete(f"action.{resource_name}.recycle_bin")
    async def recycle_bin_count(
        request: Request,
        db: DbSession,
        admin: ActiveAdmin,
    ):
        svc = service_class(db)
        count = await svc.count_deleted(delete_level=DeleteLevelEnum.ADMIN.value)
        return success(data={"count": count})

    @router.get("/recycle-bin", summary="回收站列表")
    @action_delete(f"action.{resource_name}.recycle_bin")
    async def recycle_bin_list(
        request: Request,
        db: DbSession,
        admin: ActiveAdmin,
        query: QueryParams,
    ):
        svc = service_class(db)
        items, total = await svc.query_deleted_list(
            spec=query,
            delete_level=DeleteLevelEnum.ADMIN.value,
        )
        result = [_serialize_with_delete_meta(item, _serialize) for item in items]
        return paginated(
            items=result,
            total=total,
            page=query.page,
            page_size=query.size,
        )

    @router.post("/recycle-bin/{item_id}/restore", summary="恢复记录")
    @action_delete(f"action.{resource_name}.recycle_bin")
    async def recycle_bin_restore(
        request: Request,
        db: DbSession,
        item_id: int,
        admin: ActiveAdmin,
    ):
        svc = service_class(db)
        instance = await svc.restore(item_id)
        if not instance:
            raise NotFoundException(message=_("recycle_bin.error.not_found"))
        await db.commit()
        return success(message=_("recycle_bin.restored"))

    @router.delete("/recycle-bin/{item_id}", summary="永久删除")
    @action_delete(f"action.{resource_name}.recycle_bin")
    async def recycle_bin_delete(
        request: Request,
        db: DbSession,
        item_id: int,
        admin: ActiveAdmin,
    ):
        svc = service_class(db)
        result = await svc.permanent_delete(item_id)
        if not result:
            raise NotFoundException(message=_("recycle_bin.error.not_found"))
        await db.commit()
        return deleted(message=_("recycle_bin.permanently_deleted"))

    @router.post("/recycle-bin/batch-restore", summary="批量恢复")
    @action_delete(f"action.{resource_name}.recycle_bin")
    async def recycle_bin_batch_restore(
        request: Request,
        db: DbSession,
        admin: ActiveAdmin,
        ids: list[int] = Body(..., embed=True),
    ):
        if len(ids) > _MAX_BATCH_SIZE:
            raise ValidationException(message=_("recycle_bin.error.batch_too_large"))
        svc = service_class(db)
        count = await svc.batch_restore(ids)
        await db.commit()
        return success(data={"count": count}, message=_("recycle_bin.restored"))

    @router.delete("/recycle-bin/batch", summary="批量永久删除")
    @action_delete(f"action.{resource_name}.recycle_bin")
    async def recycle_bin_batch_delete(
        request: Request,
        db: DbSession,
        admin: ActiveAdmin,
        ids: list[int] = Body(..., embed=True),
    ):
        if len(ids) > _MAX_BATCH_SIZE:
            raise ValidationException(message=_("recycle_bin.error.batch_too_large"))
        svc = service_class(db)
        count = await svc.batch_permanent_delete(ids)
        await db.commit()
        return success(data={"count": count}, message=_("recycle_bin.permanently_deleted"))


def _serialize_with_delete_meta(instance: Any, serialize_fn: Callable) -> dict:
    """序列化并自动注入回收站元数据（deleted_at / delete_level） / Serialize and auto-inject recycle bin metadata"""
    data = serialize_fn(instance)
    if "deleted_at" not in data:
        deleted_at = getattr(instance, "deleted_at", None)
        data["deleted_at"] = deleted_at or getattr(instance, "updated_at", None)
    if "delete_level" not in data:
        data["delete_level"] = getattr(instance, "delete_level", None)
    return data


def _default_serialize(instance: Any) -> dict:
    """默认序列化：调用 to_dict() / Default serializer: calls to_dict()"""
    if hasattr(instance, "to_dict"):
        return instance.to_dict()
    return {"id": getattr(instance, "id", None)}
