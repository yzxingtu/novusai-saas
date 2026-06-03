"""
管理端总回收站 API / Admin global recycle-bin API
"""

from fastapi import APIRouter, Query, Request

from app.api.shared.recycle_bin_registry import (
    build_module_metadata,
    get_module_config,
    get_recycle_bin_summary,
    get_service,
    list_global_deleted_ids,
    serialize_deleted_items,
)
from app.core.deps import ActiveAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import deleted, paginated, success
from app.enums.common import RecycleStageEnum
from app.exceptions import NotFoundException, ValidationException
from app.rbac.decorators import (
    MenuConfig,
    PermissionScope,
    action_delete,
    action_read,
    permission_resource,
)

logger = LogManager.get_logger("db")

router = APIRouter(prefix="/recycle-bin", tags=["admin-recycle-bin"])

_SIDE = "admin"
_RETIRED_CLEANUP_QUERY_PARAMS = {"retentionDays", "retention_days"}


@permission_resource(
    resource="recycle_bin",
    name="menu.admin.recycle_bin",
    scope=PermissionScope.ADMIN,
    parent_resource="system_maintenance",
    menu=MenuConfig(
        icon="lucide:trash-2",
        path="/system/recycle-bin",
        component="admin/system/recycle-bin/index",
        sort_order=99,
        parent="system_maintenance",
    ),
)
class AdminRecycleBinController:
    pass


@router.get("/modules", summary="获取管理端总回收站模块元数据")
@action_read()
async def recycle_bin_modules(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
):
    _ctx = (request, db, admin)
    return success(data=build_module_metadata(_SIDE))


@router.get("/summary", summary="获取管理端总回收站汇总")
@action_read()
async def recycle_bin_summary(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
):
    _ctx = (request, admin)
    return success(
        data=await get_recycle_bin_summary(
            db,
            _SIDE,
            aggregate_all_levels=True,
        )
    )


@router.get("", summary="按模块查询管理端总回收站记录")
@action_read()
async def recycle_bin_list(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
    query: QueryParams,
    module: str = Query(..., description=_("api.param.module")),
):
    _ctx = (request, admin)
    get_module_config(module, _SIDE)
    service = get_service(module, _SIDE, db)
    items, total = await service.query_deleted_list(
        spec=query,
        delete_level=None,
        recycle_stage=RecycleStageEnum.GLOBAL.value,
    )
    result = await serialize_deleted_items(db, module, items)
    return paginated(
        items=result,
        total=total,
        page=query.page,
        page_size=query.size,
    )


@router.post("/{module}/{item_id}/restore", summary="从管理端总回收站恢复记录")
@action_delete()
async def recycle_bin_restore(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
    module: str,
    item_id: int,
):
    _ctx = (request, admin)
    get_module_config(module, _SIDE)
    service = get_service(module, _SIDE, db)
    instance = await service.restore(
        item_id,
        recycle_stage=RecycleStageEnum.GLOBAL.value,
        delete_level=None,
    )
    if not instance:
        raise NotFoundException(message=_("recycle_bin.error.not_found"))
    await db.commit()
    return success(message=_("recycle_bin.restored"))


@router.delete("/{module}/clear", summary="清空指定模块的管理端总回收站")
@action_delete()
async def recycle_bin_clear_module(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
    module: str,
):
    _ctx = request
    get_module_config(module, _SIDE)
    service = get_service(module, _SIDE, db)
    ids = await list_global_deleted_ids(
        db,
        module,
        _SIDE,
        aggregate_all_levels=True,
    )

    count = 0
    for item_id in ids:
        if await service.permanent_delete(item_id, delete_level=None):
            count += 1

    await db.commit()
    logger.info(
        "Admin recycle-bin clear module={} admin_id={} count={}",
        module,
        admin.id,
        count,
    )
    return success(
        message=_("recycle_bin.module_cleared"),
        data={"count": count},
    )


@router.delete("/{module}/{item_id}", summary="从管理端总回收站永久删除")
@action_delete()
async def recycle_bin_permanent_delete(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
    module: str,
    item_id: int,
):
    _ctx = (request, admin)
    get_module_config(module, _SIDE)
    service = get_service(module, _SIDE, db)
    result = await service.permanent_delete(item_id, delete_level=None)
    if not result:
        raise NotFoundException(message=_("recycle_bin.error.not_found"))
    await db.commit()
    return deleted(message=_("recycle_bin.permanently_deleted"))


@router.delete("/cleanup", summary="手动触发回收站定时任务")
@action_delete()
async def recycle_bin_cleanup(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
    module_retention_days: int | None = Query(default=None, ge=1, le=365),
    global_retention_days: int | None = Query(default=None, ge=1, le=365),
):
    _ctx = (request, db, admin)
    if _RETIRED_CLEANUP_QUERY_PARAMS.intersection(request.query_params):
        raise ValidationException(message=_("recycle_bin.error.retired_retention_days"))

    from app.tasks.recycle_bin import cleanup_recycle_bin

    kwargs: dict[str, int] = {}
    if module_retention_days is not None:
        kwargs["module_retention_days"] = module_retention_days
    if global_retention_days is not None:
        kwargs["global_retention_days"] = global_retention_days

    result = cleanup_recycle_bin.delay(**kwargs)
    return success(
        data={"task_id": str(result.id)},
        message=_("recycle_bin.cleanup_triggered"),
    )
