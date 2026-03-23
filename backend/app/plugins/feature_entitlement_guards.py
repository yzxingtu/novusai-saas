"""Built-in guards for feature-managed plugin prerequisites.

Provides host-side preflight and lifecycle veto rules for plugins that are
controlled by tenant plan feature flags.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select

from app.core.database import async_session_factory
from app.enums.plugin import PluginStatusEnum
from app.models.system.plugin import Plugin
from app.models.tenant.tenant_plan import TenantPlan

STORAGE_BILLING_FEATURE = "storage_billing_enabled"
STORAGE_BILLING_PLUGIN = "storage-billing"
STORAGE_BILLING_DRIVER_PLUGINS = (
    "qiniu-kodo",
    "aliyun-oss",
    "tencent-cos",
)
_OWNER = "host.feature_entitlement_guards"


def _is_flag_enabled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


async def _get_plugin_status_map(plugin_names: Iterable[str]) -> dict[str, str]:
    names = [str(name).strip() for name in plugin_names if str(name).strip()]
    if not names:
        return {}

    async with async_session_factory() as db:
        result = await db.execute(
            select(Plugin.name, Plugin.status).where(
                Plugin.name.in_(names),
                Plugin.is_deleted.is_(False),
            )
        )
        return {
            str(name): str(status or "")
            for name, status in result.all()
        }


async def _get_active_feature_plan_summaries(feature_flag: str) -> list[dict[str, Any]]:
    async with async_session_factory() as db:
        result = await db.execute(
            select(TenantPlan.id, TenantPlan.name, TenantPlan.features).where(
                TenantPlan.is_active.is_(True),
                TenantPlan.is_deleted.is_(False),
            )
        )

        plans: list[dict[str, Any]] = []
        for plan_id, name, features in result.all():
            feature_map = dict(features or {})
            if not _is_flag_enabled(feature_map.get(feature_flag)):
                continue
            plans.append(
                {
                    "plan_id": int(plan_id),
                    "plan_name": str(name or ""),
                    "features": feature_map,
                }
            )
        return plans


async def _storage_billing_plan_preflight(payload) -> dict[str, Any] | None:
    features = dict(payload.get("features") or {})
    if not _is_flag_enabled(features.get(STORAGE_BILLING_FEATURE)):
        return None

    tracked_plugins = [STORAGE_BILLING_PLUGIN, *STORAGE_BILLING_DRIVER_PLUGINS]
    status_map = await _get_plugin_status_map(tracked_plugins)
    storage_billing_status = status_map.get(STORAGE_BILLING_PLUGIN, "")
    enabled_driver_plugins = [
        name
        for name in STORAGE_BILLING_DRIVER_PLUGINS
        if status_map.get(name) == PluginStatusEnum.ENABLED.value
    ]

    if storage_billing_status != PluginStatusEnum.ENABLED.value:
        return {
            "allowed": False,
            "reason_code": "storage_billing_plugin_unavailable",
            "message": "Storage billing feature requires the storage-billing plugin to be enabled.",
            "details": {
                "required_plugin": STORAGE_BILLING_PLUGIN,
                "required_any_plugins": list(STORAGE_BILLING_DRIVER_PLUGINS),
                "plugin_status": storage_billing_status or "missing",
                "enabled_driver_plugins": enabled_driver_plugins,
            },
        }

    if not enabled_driver_plugins:
        return {
            "allowed": False,
            "reason_code": "storage_billing_missing_cloud_storage_plugin",
            "message": (
                "Storage billing feature requires at least one enabled cloud storage plugin: "
                "qiniu-kodo, aliyun-oss, or tencent-cos."
            ),
            "details": {
                "required_plugin": STORAGE_BILLING_PLUGIN,
                "required_any_plugins": list(STORAGE_BILLING_DRIVER_PLUGINS),
                "plugin_status": storage_billing_status,
                "enabled_driver_plugins": enabled_driver_plugins,
            },
        }

    return None


async def _feature_managed_lifecycle_guard(payload) -> dict[str, Any] | None:
    plugin_name = str(payload.get("plugin_name") or "").strip()
    if plugin_name not in {STORAGE_BILLING_PLUGIN, *STORAGE_BILLING_DRIVER_PLUGINS}:
        return None

    active_plans = await _get_active_feature_plan_summaries(STORAGE_BILLING_FEATURE)
    if not active_plans:
        return None

    if plugin_name == STORAGE_BILLING_PLUGIN:
        return {
            "allowed": False,
            "reason_code": "storage_billing_feature_in_use",
            "message": "Storage-billing cannot be disabled or uninstalled while active plans still enable storage billing.",
            "details": {
                "feature_flag": STORAGE_BILLING_FEATURE,
                "active_plan_ids": [item["plan_id"] for item in active_plans],
                "active_plan_count": len(active_plans),
            },
        }

    status_map = await _get_plugin_status_map(STORAGE_BILLING_DRIVER_PLUGINS)
    other_enabled_drivers = [
        name
        for name in STORAGE_BILLING_DRIVER_PLUGINS
        if name != plugin_name and status_map.get(name) == PluginStatusEnum.ENABLED.value
    ]
    if other_enabled_drivers:
        return None

    return {
        "allowed": False,
        "reason_code": "storage_billing_last_driver_blocked",
        "message": (
            "The last enabled cloud storage billing dependency cannot be disabled "
            "or uninstalled while storage billing is still enabled in active plans."
        ),
        "details": {
            "feature_flag": STORAGE_BILLING_FEATURE,
            "required_any_plugins": list(STORAGE_BILLING_DRIVER_PLUGINS),
            "active_plan_ids": [item["plan_id"] for item in active_plans],
            "active_plan_count": len(active_plans),
        },
    }


def ensure_feature_entitlement_guards_registered() -> None:
    from app.plugins.lifecycle_guards import get_plugin_lifecycle_guard_registry
    from app.plugins.tenant_plan_preflight import get_tenant_plan_preflight_registry

    get_tenant_plan_preflight_registry().register(
        _OWNER,
        _storage_billing_plan_preflight,
        priority=20,
    )
    get_plugin_lifecycle_guard_registry().register(
        _OWNER,
        _feature_managed_lifecycle_guard,
        priority=20,
    )


__all__ = [
    "ensure_feature_entitlement_guards_registered",
]
