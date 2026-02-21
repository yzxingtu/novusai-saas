"""
管理端总回收站 API

聚合展示所有模块的已删除记录，支持按模块筛选、恢复、升级、永久删除。
支持：
- 区分管理端/租户级记录（is_tenant + tenant_name）
- 继承原模块 __filterable__/__sortable__ 搜索能力
"""

from typing import Any

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute

from app.core.deps import DbSession, ActiveAdmin, QueryParams
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import success, deleted, paginated
from app.exceptions import NotFoundException, ValidationException
from app.rbac.decorators import (
    permission_resource, action_read, action_delete,
    PermissionScope, MenuConfig,
)

logger = LogManager.get_logger("db")

router = APIRouter(prefix="/recycle-bin", tags=["admin-recycle-bin"])

_MAX_BATCH_SIZE = 100


# ── 可回收模块注册表 ──
# columns: 前端需要展示的字段列表（id / deleted_at / delete_level / tenant_name 由框架自动附加）
RECYCLABLE_MODULES: dict[str, dict[str, Any]] = {
    "ai_providers": {
        "model": "app.models.ai.provider.AIProvider",
        "service": "app.services.ai.provider_service.AIProviderService",
        "label_field": "name",
        "i18n_key": "deletion.model.ai_provider",
        "is_tenant": False,
        "columns": ["name", "code", "status"],
    },
    "ai_models": {
        "model": "app.models.ai.model.AIModel",
        "service": "app.services.ai.model_service.AIModelService",
        "label_field": "name",
        "i18n_key": "deletion.model.ai_model",
        "is_tenant": False,
        "columns": ["name", "model_id", "provider_id", "status"],
    },
    "agents": {
        "model": "app.models.ai.agent.Agent",
        "service": "app.services.ai.agent_service.AgentService",
        "label_field": "name",
        "i18n_key": "deletion.model.agent",
        "is_tenant": True,
        "columns": ["name", "status"],
    },
    "skill_packages": {
        "model": "app.models.ai.skill_package.SkillPackage",
        "service": "app.services.ai.skill_package_service.SkillPackageService",
        "label_field": "name",
        "i18n_key": "deletion.model.skill_package",
        "is_tenant": True,
        "columns": ["name", "scope", "status"],
    },
    "knowledge_bases": {
        "model": "app.models.ai.knowledge_base.KnowledgeBase",
        "service": "app.services.ai.knowledge_base_service.KnowledgeBaseService",
        "label_field": "name",
        "i18n_key": "deletion.model.knowledge_base",
        "is_tenant": True,
        "columns": ["name", "status"],
    },
    "admin_roles": {
        "model": "app.models.auth.admin_role.AdminRole",
        "service": "app.services.system.admin_role_service.AdminRoleService",
        "label_field": "name",
        "i18n_key": "deletion.model.admin_role",
        "is_tenant": False,
        "columns": ["name", "code"],
    },
    "tenant_plans": {
        "model": "app.models.tenant.tenant_plan.TenantPlan",
        "service": "app.services.tenant.tenant_plan_service.TenantPlanService",
        "label_field": "name",
        "i18n_key": "deletion.model.tenant_plan",
        "is_tenant": False,
        "columns": ["name", "code", "status"],
    },
    "tenants": {
        "model": "app.models.tenant.tenant.Tenant",
        "service": "app.services.system.tenant_service.TenantService",
        "label_field": "name",
        "i18n_key": "deletion.model.tenant",
        "is_tenant": False,
        "columns": ["name", "code", "status"],
    },
    "tenant_domains": {
        "model": "app.models.tenant.tenant_domain.TenantDomain",
        "service": "app.services.system.tenant_domain_service.TenantDomainService",
        "label_field": "domain",
        "i18n_key": "deletion.model.tenant_domain",
        "is_tenant": True,
        "columns": ["domain"],
    },
    "table_policies": {
        "model": "app.models.ai.table_policy.AITablePolicy",
        "service": "app.services.ai.table_policy_service.AITablePolicyService",
        "label_field": "table_name",
        "i18n_key": "deletion.model.table_policy",
        "is_tenant": False,
        "columns": ["table_name", "label"],
    },
}

# ── 模块类缓存 ──
_model_cache: dict[str, type] = {}
_svc_cache: dict[str, type] = {}


def _import_class(path: str):
    """动态导入类"""
    import importlib
    module_path, class_name = path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _get_model(module_code: str):
    """获取并缓存模块的 Model 类"""
    if module_code not in _model_cache:
        config = RECYCLABLE_MODULES[module_code]
        _model_cache[module_code] = _import_class(config["model"])
    return _model_cache[module_code]


def _get_service(module_code: str, db: Any):
    """获取模块对应的 Service 实例

    TenantService 子类需要 tenant_id，但管理端总回收站跨租户查询，
    因此对 TenantService 子类动态构建基于 BaseRepository 的
    GlobalService（无租户隔离），并继承原模型的 __filterable__ /
    __sortable__ 搜索能力，同时额外开放 tenant_id 过滤。
    """
    from app.core.base_repository import BaseRepository
    from app.core.base_service import TenantService as _TenantSvc, GlobalService

    config = RECYCLABLE_MODULES.get(module_code)
    if not config:
        raise ValidationException(
            message=_("recycle_bin.error.invalid_module"),
        )
    svc_class = _import_class(config["service"])

    if issubclass(svc_class, _TenantSvc):
        model_cls = _get_model(module_code)

        class _CrossTenantRepo(BaseRepository):
            model = model_cls

            def get_allowed_fields(self, scope=None):
                """继承原模型 __filterable__ 并额外开放 tenant_id"""
                fields = super().get_allowed_fields(scope)
                if hasattr(self.model, "tenant_id") and "tenant_id" not in fields:
                    fields["tenant_id"] = self.model.tenant_id
                return fields

        class _CrossTenantService(GlobalService):
            repository_class = _CrossTenantRepo
            model_class = model_cls

        return _CrossTenantService(db)

    return svc_class(db)


def _model_to_dict(instance: Any, columns: list[str]) -> dict[str, Any]:
    """将模型实例序列化为 dict，仅包含指定列 + 通用字段"""
    data: dict[str, Any] = {"id": instance.id}
    for col in columns:
        val = getattr(instance, col, None)
        data[col] = val
    data["deleted_at"] = getattr(instance, "deleted_at", None)
    data["delete_level"] = getattr(instance, "delete_level", None)
    if hasattr(instance, "tenant_id"):
        data["tenant_id"] = instance.tenant_id
    return data


async def _batch_resolve_tenant_names(
    db: Any,
    tenant_ids: set[int],
) -> dict[int, str]:
    """批量查询 tenant_id → tenant_name 映射"""
    if not tenant_ids:
        return {}
    from app.models.tenant.tenant import Tenant
    stmt = select(Tenant.id, Tenant.name).where(Tenant.id.in_(list(tenant_ids)))
    rows = (await db.execute(stmt)).all()
    return {row[0]: row[1] for row in rows}


@permission_resource(
    resource="recycle_bin",
    name="menu.admin.recycle_bin",
    scope=PermissionScope.ADMIN,
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


# ──────────────────── 模块元数据 ────────────────────

@router.get("/modules", summary="获取所有可回收模块元数据")
@action_read()
async def recycle_bin_modules(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
):
    """
    返回各模块的元数据：label、is_tenant、columns、filterable fields。
    前端据此渲染动态列和搜索表单。
    """
    result = {}
    for code, config in RECYCLABLE_MODULES.items():
        model_cls = _get_model(code)
        filterable = getattr(model_cls, "__filterable__", {})
        # 对租户模型额外开放 tenant_id
        if config.get("is_tenant") and "tenant_id" not in filterable:
            filterable = {**filterable, "tenant_id": "tenant_id"}
        result[code] = {
            "label": _(config["i18n_key"]),
            "is_tenant": config.get("is_tenant", False),
            "columns": config["columns"],
            "label_field": config["label_field"],
            "filterable": list(filterable.keys()),
        }
    return success(data=result)


# ──────────────────── 汇总 ────────────────────

@router.get("/summary", summary="各模块已删除记录数统计")
@action_read()
async def recycle_bin_summary(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
):
    """返回各模块在 admin 回收站中的已删除记录数"""
    results = []
    for code, config in RECYCLABLE_MODULES.items():
        try:
            model_cls = _get_model(code)
            if not hasattr(model_cls, "is_deleted"):
                continue

            stmt = (
                select(func.count())
                .select_from(model_cls)
                .where(model_cls.is_deleted.is_(True))
            )
            count = (await db.execute(stmt)).scalar() or 0

            if count > 0:
                results.append({
                    "module": code,
                    "label": _(config["i18n_key"]),
                    "count": count,
                    "is_tenant": config.get("is_tenant", False),
                })
        except Exception as e:
            logger.warning("Failed to count %s: %s", code, e)

    return success(data=results)


# ──────────────────── 列表（支持搜索） ────────────────────

@router.get("", summary="按模块查询已删除记录")
@action_read()
async def recycle_bin_list(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
    query: QueryParams,
    module: str = Query(..., description="模块代码"),
):
    """
    查询指定模块的已删除记录。

    搜索/排序继承原模块的 __filterable__ / __sortable__ 定义。
    租户级记录自动附带 tenant_id / tenant_name。
    """
    config = RECYCLABLE_MODULES.get(module)
    if not config:
        raise ValidationException(
            message=_("recycle_bin.error.invalid_module"),
        )

    svc = _get_service(module, db)
    items, total = await svc.query_deleted_list(spec=query)

    columns = config["columns"]
    is_tenant = config.get("is_tenant", False)

    result = [_model_to_dict(item, columns) for item in items]

    # 批量解析租户名称
    if is_tenant:
        tenant_ids = {r["tenant_id"] for r in result if r.get("tenant_id")}
        name_map = await _batch_resolve_tenant_names(db, tenant_ids)
        for r in result:
            r["tenant_name"] = name_map.get(r.get("tenant_id"), "")

    return paginated(
        items=result,
        total=total,
        page=query.page,
        page_size=query.size,
    )


# ──────────────────── 恢复 / 永久删除 / 清理 ────────────────────

@router.post("/{module}/{item_id}/restore", summary="恢复记录")
@action_delete()
async def recycle_bin_restore(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
    module: str,
    item_id: int,
):
    svc = _get_service(module, db)
    instance = await svc.restore(item_id)
    if not instance:
        raise NotFoundException(message=_("recycle_bin.error.not_found"))
    await db.commit()
    return success(message=_("recycle_bin.restored"))


@router.delete("/{module}/{item_id}", summary="永久删除")
@action_delete()
async def recycle_bin_permanent_delete(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
    module: str,
    item_id: int,
):
    svc = _get_service(module, db)
    result = await svc.permanent_delete(item_id)
    if not result:
        raise NotFoundException(message=_("recycle_bin.error.not_found"))
    await db.commit()
    return deleted(message=_("recycle_bin.permanently_deleted"))


@router.delete("/cleanup", summary="手动触发过期清理")
@action_delete()
async def recycle_bin_cleanup(
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
    retention_days: int = Query(default=30, ge=1, le=365),
):
    """手动触发回收站过期记录清理"""
    from app.tasks.recycle_bin import cleanup_recycle_bin
    result = cleanup_recycle_bin.delay(retention_days=retention_days)
    return success(
        data={"task_id": str(result.id)},
        message=_("recycle_bin.cleanup_triggered"),
    )
