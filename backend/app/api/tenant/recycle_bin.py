"""
租户端总回收站 API / Tenant Recycle Bin API

聚合展示当前租户所有模块的 tenant 级已删除记录，支持恢复和升级到管理端。
Aggregate display of current tenant's tenant-level deleted records, supports restore and escalation to admin.
"""

from typing import Any

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

from app.core.deps import ActiveTenantAdmin, DbSession, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import paginated, success
from app.enums.common import DeleteLevelEnum
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException, ValidationException
from app.rbac.decorators import (
    MenuConfig,
    action_delete,
    action_read,
    permission_resource,
)

logger = LogManager.get_logger("db")

router = APIRouter(prefix="/recycle-bin", tags=["tenant-recycle-bin"])


# ── 租户端可回收模块注册表 / Tenant Recyclable Module Registry ──
TENANT_RECYCLABLE_MODULES: dict[str, dict[str, Any]] = {
    "agents": {
        "model": "app.models.ai.agent.Agent",
        "service": "app.services.ai.agent_service.AgentService",
        "label_field": "name",
        "i18n_key": "deletion.model.agent",
        "columns": ["name", "status"],
    },
    "knowledge_bases": {
        "model": "app.models.ai.knowledge_base.KnowledgeBase",
        "service": "app.services.ai.knowledge_base_service.KnowledgeBaseService",
        "label_field": "name",
        "i18n_key": "deletion.model.knowledge_base",
        "columns": ["name", "status"],
    },
    "periodic_tasks": {
        "model": "app.models.system.periodic_task.PeriodicTask",
        "service": "app.services.tenant.periodic_task_service.TenantPeriodicTaskService",
        "label_field": "name",
        "i18n_key": "deletion.model.periodic_task",
        "columns": ["name", "is_active"],
    },
}


_model_cache: dict[str, type] = {}
_svc_cache: dict[str, type] = {}


def _import_class(path: str):
    import importlib
    module_path, class_name = path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _get_model(module_code: str):
    if module_code not in _model_cache:
        config = TENANT_RECYCLABLE_MODULES[module_code]
        _model_cache[module_code] = _import_class(config["model"])
    return _model_cache[module_code]


def _get_service(module_code: str, db: Any, tenant_id: int):
    config = TENANT_RECYCLABLE_MODULES.get(module_code)
    if not config:
        raise ValidationException(message=_("recycle_bin.error.invalid_module"))
    svc_class = _import_class(config["service"])
    return svc_class(db, tenant_id)


def _model_to_dict(instance: Any, columns: list[str]) -> dict[str, Any]:
    data: dict[str, Any] = {"id": instance.id}
    for col in columns:
        data[col] = getattr(instance, col, None)
    data["deleted_at"] = getattr(instance, "deleted_at", None)
    data["delete_level"] = getattr(instance, "delete_level", None)
    return data


@permission_resource(
    resource="tenant_recycle_bin",
    name="menu.tenant.recycle_bin",
    scope=PermissionScope.ALL_TENANTS,
    parent_resource="system_maintenance",
    menu=MenuConfig(
        icon="lucide:trash-2",
        path="/system/recycle-bin",
        component="tenant/system/recycle-bin/index",
        sort_order=99,
        parent="system_maintenance",
    ),
)
class TenantRecycleBinController:
    pass


@router.get("/modules", summary="获取所有可回收模块元数据")
@action_read("action.tenant_recycle_bin.list")
async def recycle_bin_modules(
    request: Request,
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    result = {}
    for code, config in TENANT_RECYCLABLE_MODULES.items():
        result[code] = {
            "label": _(config["i18n_key"]),
            "columns": config["columns"],
            "label_field": config["label_field"],
        }
    return success(data=result)


@router.get("/summary", summary="各模块已删除记录数统计")
@action_read("action.tenant_recycle_bin.list")
async def recycle_bin_summary(
    request: Request,
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    results = []
    for code, config in TENANT_RECYCLABLE_MODULES.items():
        try:
            model_cls = _get_model(code)
            if not hasattr(model_cls, "is_deleted"):
                continue

            conditions = [
                model_cls.is_deleted.is_(True),
                model_cls.delete_level == DeleteLevelEnum.TENANT.value,
            ]
            if hasattr(model_cls, "tenant_id"):
                conditions.append(model_cls.tenant_id == tenant_admin.tenant_id)

            stmt = (
                select(func.count())
                .select_from(model_cls)
                .where(*conditions)
            )
            count = (await db.execute(stmt)).scalar() or 0

            if count > 0:
                results.append({
                    "module": code,
                    "label": _(config["i18n_key"]),
                    "count": count,
                })
        except Exception as e:
            logger.warning("Failed to count %s: %s", code, e)

    return success(data=results)


@router.get("", summary="按模块查询已删除记录")
@action_read("action.tenant_recycle_bin.list")
async def recycle_bin_list(
    request: Request,
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
    query: QueryParams,
    module: str = Query(..., description="模块代码"),
):
    config = TENANT_RECYCLABLE_MODULES.get(module)
    if not config:
        raise ValidationException(message=_("recycle_bin.error.invalid_module"))

    svc = _get_service(module, db, tenant_admin.tenant_id)
    items, total = await svc.query_deleted_list(
        spec=query,
        delete_level=DeleteLevelEnum.TENANT.value,
    )

    columns = config["columns"]
    result = [_model_to_dict(item, columns) for item in items]

    return paginated(
        items=result,
        total=total,
        page=query.page,
        page_size=query.size,
    )


@router.post("/{module}/{item_id}/restore", summary="恢复记录")
@action_delete("action.tenant_recycle_bin.manage")
async def recycle_bin_restore(
    request: Request,
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
    module: str,
    item_id: int,
):
    svc = _get_service(module, db, tenant_admin.tenant_id)
    instance = await svc.restore(item_id)
    if not instance:
        raise NotFoundException(message=_("recycle_bin.error.not_found"))
    await db.commit()
    return success(message=_("recycle_bin.restored"))


@router.delete("/{module}/{item_id}", summary="从回收站移出（升级到管理端）")
@action_delete("action.tenant_recycle_bin.manage")
async def recycle_bin_escalate(
    request: Request,
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
    module: str,
    item_id: int,
):
    svc = _get_service(module, db, tenant_admin.tenant_id)
    instance = await svc.escalate_delete(item_id)
    if not instance:
        raise NotFoundException(message=_("recycle_bin.error.not_found"))
    await db.commit()
    return success(message=_("recycle_bin.escalated"))
