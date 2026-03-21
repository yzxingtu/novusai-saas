"""
Shared recycle-bin registry and helpers / 共享回收站注册表与辅助函数
"""

from __future__ import annotations

import importlib
from typing import Any, Literal

from sqlalchemy import select

from app.core.i18n import _
from app.enums.common import DeleteLevelEnum, RecycleStageEnum
from app.exceptions import ValidationException
from app.models.tenant.tenant import Tenant

RecycleBinSide = Literal["admin", "tenant"]


RECYCLABLE_MODULES: dict[str, dict[str, Any]] = {
    "ai_providers": {
        "model": "app.models.ai.provider.AIProvider",
        "label_field": "name",
        "i18n_key": "deletion.model.ai_provider",
        "columns": ["name", "code", "type", "is_active", "created_at"],
        "services": {
            "admin": "app.services.ai.provider_service.AIProviderService",
        },
    },
    "ai_models": {
        "model": "app.models.ai.model.AIModel",
        "label_field": "name",
        "i18n_key": "deletion.model.ai_model",
        "columns": [
            "name",
            "code",
            "type",
            "provider_name",
            "context_window",
            "input_price_per_1k",
            "tier",
            "is_active",
            "created_at",
        ],
        "services": {
            "admin": "app.services.ai.model_service.AIModelService",
        },
    },
    "ai_api_keys": {
        "model": "app.models.ai.api_key.ProviderApiKey",
        "label_field": "name",
        "i18n_key": "deletion.model.provider_api_key",
        "columns": ["name", "provider_id"],
        "services": {
            "admin": "app.services.ai.api_key_service.ProviderApiKeyService",
        },
    },
    "agents": {
        "model": "app.models.ai.agent.Agent",
        "label_field": "name",
        "i18n_key": "deletion.model.agent",
        "columns": [
            "name",
            "status",
            "visibility",
            "execution_mode",
            "scope",
            "description",
            "created_at",
        ],
        "services": {
            "admin": "app.services.ai.agent_service.AdminAgentService",
            "tenant": "app.services.ai.agent_service.AgentService",
        },
    },
    "knowledge_bases": {
        "model": "app.models.ai.knowledge_base.KnowledgeBase",
        "label_field": "name",
        "i18n_key": "deletion.model.knowledge_base",
        "columns": [
            "name",
            "status",
            "document_count",
            "total_chunks",
            "total_size_bytes",
            "scope",
            "description",
            "created_at",
        ],
        "services": {
            "admin": "app.services.ai.knowledge_base_service.AdminKnowledgeBaseService",
            "tenant": "app.services.ai.knowledge_base_service.KnowledgeBaseService",
        },
    },
    "skill_packages": {
        "model": "app.models.ai.skill_package.SkillPackage",
        "label_field": "name",
        "i18n_key": "deletion.model.skill_package",
        "columns": ["name", "is_active", "target_audience"],
        "services": {
            "admin": "app.services.ai.skill_package_service.AdminSkillPackageService",
        },
    },
    "periodic_tasks": {
        "model": "app.models.system.periodic_task.PeriodicTask",
        "label_field": "name",
        "i18n_key": "deletion.model.periodic_task",
        "columns": [
            "name",
            "task_path",
            "schedule_type",
            "cron_expression",
            "interval_seconds",
            "is_active",
            "last_run_at",
            "next_run_at",
            "created_at",
        ],
        "services": {
            "admin": "app.services.system.periodic_task_service.PeriodicTaskService",
            "tenant": "app.services.tenant.periodic_task_service.TenantPeriodicTaskService",
        },
    },
    "tenant_plans": {
        "model": "app.models.tenant.tenant_plan.TenantPlan",
        "label_field": "name",
        "i18n_key": "deletion.model.tenant_plan",
        "columns": ["name", "code", "price", "billing_cycle", "is_active", "created_at"],
        "services": {
            "admin": "app.services.tenant.tenant_plan_service.TenantPlanService",
        },
    },
    "admin_roles": {
        "model": "app.models.auth.admin_role.AdminRole",
        "label_field": "name",
        "i18n_key": "deletion.model.admin_role",
        "columns": ["name", "code"],
        "services": {
            "admin": "app.services.system.admin_role_service.AdminRoleService",
        },
    },
    "tenants": {
        "model": "app.models.tenant.tenant.Tenant",
        "label_field": "name",
        "i18n_key": "deletion.model.tenant",
        "columns": [
            "name",
            "code",
            "contact_name",
            "contact_phone",
            "is_active",
            "expires_at",
            "created_at",
        ],
        "services": {
            "admin": "app.services.system.tenant_service.TenantService",
        },
    },
}

_model_cache: dict[str, type] = {}
_service_cache: dict[str, type] = {}


def _import_class(path: str):
    module_path, class_name = path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _normalize_field_keys(config: Any) -> list[str]:
    if not config:
        return []
    if isinstance(config, dict):
        if "field" in config:
            return []
        return list(config.keys())
    if isinstance(config, (list, set, tuple)):
        return list(config)
    return []


def _recycle_column_label(module_code: str, field: str) -> str:
    for key in (
        f"recycle_bin.column.{module_code}.{field}",
        f"recycle_bin.column.common.{field}",
    ):
        text = _(key)
        if text != key:
            return text
    return ""


def _build_column_labels(
    module_code: str,
    config: dict[str, Any],
    filterable_keys: list[str],
    sortable_keys: list[str],
) -> dict[str, str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for field in list(config.get("columns") or []) + filterable_keys + sortable_keys:
        if field in seen:
            continue
        seen.add(field)
        ordered.append(field)

    labels: dict[str, str] = {}
    for field in ordered:
        label = _recycle_column_label(module_code, field)
        if label:
            labels[field] = label
    return labels


def get_module_codes_for_side(side: RecycleBinSide) -> list[str]:
    return [
        module_code
        for module_code, config in RECYCLABLE_MODULES.items()
        if side in config.get("services", {})
    ]


def get_module_config(
    module_code: str,
    side: RecycleBinSide,
) -> dict[str, Any]:
    config = RECYCLABLE_MODULES.get(module_code)
    if not config or side not in config.get("services", {}):
        raise ValidationException(message=_("recycle_bin.error.invalid_module"))
    return config


def get_model(module_code: str) -> type:
    if module_code not in _model_cache:
        _model_cache[module_code] = _import_class(RECYCLABLE_MODULES[module_code]["model"])
    return _model_cache[module_code]


def get_service(
    module_code: str,
    side: RecycleBinSide,
    db: Any,
    tenant_id: int | None = None,
):
    config = get_module_config(module_code, side)
    service_path = config["services"][side]
    if service_path not in _service_cache:
        _service_cache[service_path] = _import_class(service_path)
    service_class = _service_cache[service_path]

    if side == "tenant":
        if tenant_id is None:
            raise ValidationException(message=_("recycle_bin.error.invalid_module"))
        return service_class(db, tenant_id)
    return service_class(db)


def get_delete_scope(side: RecycleBinSide) -> str:
    return (
        DeleteLevelEnum.ADMIN.value
        if side == "admin"
        else DeleteLevelEnum.TENANT.value
    )


def get_tenant_field_name(model_cls: type) -> str | None:
    if hasattr(model_cls, "owner_tenant_id"):
        return "owner_tenant_id"
    if hasattr(model_cls, "tenant_id"):
        return "tenant_id"
    return None


def build_module_metadata(side: RecycleBinSide) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for module_code in get_module_codes_for_side(side):
        config = RECYCLABLE_MODULES[module_code]
        model_cls = get_model(module_code)
        tenant_field = get_tenant_field_name(model_cls)

        filterable_keys = _normalize_field_keys(getattr(model_cls, "__filterable__", {}))
        if side == "admin" and tenant_field and tenant_field not in filterable_keys:
            filterable_keys.append(tenant_field)

        sortable_keys = _normalize_field_keys(getattr(model_cls, "__sortable__", {}))
        if "deleted_at" not in sortable_keys:
            sortable_keys.append("deleted_at")
        if "promoted_to_global_at" not in sortable_keys:
            sortable_keys.append("promoted_to_global_at")

        result[module_code] = {
            "label": _(config["i18n_key"]),
            "is_tenant": tenant_field is not None,
            "tenant_field": tenant_field,
            "columns": config["columns"],
            "label_field": config["label_field"],
            "filterable": filterable_keys,
            "sortable": sortable_keys,
            "column_labels": _build_column_labels(
                module_code,
                config,
                filterable_keys,
                sortable_keys,
            ),
        }
    return result


def serialize_deleted_item(module_code: str, instance: Any) -> dict[str, Any]:
    config = RECYCLABLE_MODULES[module_code]
    model_cls = instance.__class__
    tenant_field = get_tenant_field_name(model_cls)

    data: dict[str, Any] = {"id": getattr(instance, "id", None)}
    for field in config["columns"]:
        data[field] = getattr(instance, field, None)

    data["deleted_at"] = getattr(instance, "deleted_at", None)
    data["delete_level"] = getattr(instance, "delete_level", None)
    data["recycle_stage"] = getattr(instance, "recycle_stage", None)
    data["promoted_to_global_at"] = getattr(instance, "promoted_to_global_at", None)

    if tenant_field:
        tenant_value = getattr(instance, tenant_field, None)
        data["tenant_id"] = tenant_value
        if tenant_field != "tenant_id":
            data[tenant_field] = tenant_value

    return data


async def serialize_deleted_items(
    db: Any,
    module_code: str,
    items: list[Any],
) -> list[dict[str, Any]]:
    result = [serialize_deleted_item(module_code, item) for item in items]
    tenant_ids = {
        int(row["tenant_id"])
        for row in result
        if row.get("tenant_id") is not None
    }
    if not tenant_ids:
        return result

    rows = await db.execute(
        select(Tenant.id, Tenant.name).where(Tenant.id.in_(list(tenant_ids)))
    )
    name_map = {row[0]: row[1] for row in rows.all()}
    for row in result:
        tenant_id = row.get("tenant_id")
        if tenant_id is not None:
            row["tenant_name"] = name_map.get(int(tenant_id), "")
    return result


async def get_recycle_bin_summary(
    db: Any,
    side: RecycleBinSide,
    tenant_id: int | None = None,
    aggregate_all_levels: bool = False,
) -> list[dict[str, Any]]:
    delete_scope = None if aggregate_all_levels else get_delete_scope(side)
    results: list[dict[str, Any]] = []
    for module_code in get_module_codes_for_side(side):
        service = get_service(module_code, side, db, tenant_id=tenant_id)
        count = await service.count_deleted(
            delete_level=delete_scope,
            recycle_stage=RecycleStageEnum.GLOBAL.value,
        )
        if count <= 0:
            continue

        config = RECYCLABLE_MODULES[module_code]
        results.append(
            {
                "module": module_code,
                "label": _(config["i18n_key"]),
                "count": count,
                "is_tenant": get_tenant_field_name(get_model(module_code)) is not None,
            }
        )

    results.sort(key=lambda item: (-int(item["count"]), str(item["label"])))
    return results


async def list_global_deleted_ids(
    db: Any,
    module_code: str,
    side: RecycleBinSide,
    tenant_id: int | None = None,
    aggregate_all_levels: bool = False,
) -> list[int]:
    model_cls = get_model(module_code)
    stmt = select(model_cls.id).where(
        model_cls.is_deleted.is_(True),
        model_cls.recycle_stage == RecycleStageEnum.GLOBAL.value,
    )

    if not aggregate_all_levels:
        stmt = stmt.where(model_cls.delete_level == get_delete_scope(side))

    tenant_field = get_tenant_field_name(model_cls)
    if side == "tenant" and tenant_id is not None and tenant_field:
        stmt = stmt.where(getattr(model_cls, tenant_field) == tenant_id)

    result = await db.execute(stmt.order_by(model_cls.id))
    return list(result.scalars().all())


__all__ = [
    "RECYCLABLE_MODULES",
    "RecycleBinSide",
    "build_module_metadata",
    "get_delete_scope",
    "get_model",
    "get_module_codes_for_side",
    "get_module_config",
    "get_recycle_bin_summary",
    "get_service",
    "get_tenant_field_name",
    "list_global_deleted_ids",
    "serialize_deleted_items",
]
