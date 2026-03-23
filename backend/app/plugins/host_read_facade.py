"""
Host read-only facade for plugin sandbox.
/
插件沙箱的宿主只读门面。

Provides controlled read-only snapshots from host core modules.
No raw session or arbitrary SQL is exposed to plugins.
/
提供宿主核心模块的受控只读快照。
不向插件暴露原始 session 或任意 SQL 能力。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.system.plugin import Plugin
from app.models.tenant.tenant import Tenant
from app.models.tenant.tenant_plan import TenantPlan
from app.services.common.storage_config_resolver import StorageConfigResolver
from app.storage.manager import storage_manager


def _serialize_decimal(value: Decimal | int | float | None) -> float | int | None:
    """Serialize Decimal values for JSON-safe snapshots. / 将 Decimal 序列化为 JSON 安全值。"""
    if isinstance(value, Decimal):
        return float(value)
    return value


def _serialize_plan(plan: TenantPlan) -> dict[str, Any]:
    """Build a read-only plan snapshot. / 构建套餐只读快照。"""
    return {
        "id": plan.id,
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "price": _serialize_decimal(plan.price),
        "billing_cycle": plan.billing_cycle,
        "is_active": bool(plan.is_active),
        "sort_order": plan.sort_order,
        "quota": plan.quota or {},
        "features": plan.features or {},
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


class HostReadFacade:
    """
    Read-only facade exposed to plugin runtime.
    /
    暴露给插件运行时的只读门面。
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_enabled_storage_drivers(self) -> list[dict[str, Any]]:
        """
        Return currently available storage drivers with plugin ownership hints.
        / 返回当前可用存储驱动及其插件归属提示。
        """
        result = await self._db.execute(
            select(Plugin.name, Plugin.status, Plugin.manifest).where(
                Plugin.is_deleted.is_(False),
            )
        )

        driver_owner_map: dict[str, dict[str, str]] = {}
        for plugin_name, plugin_status, manifest_data in result.all():
            manifest = manifest_data or {}
            extensions = manifest.get("extensions", {}) if isinstance(manifest, dict) else {}
            storage_drivers = extensions.get("storage_drivers", []) if isinstance(extensions, dict) else []
            if not isinstance(storage_drivers, list):
                continue
            for item in storage_drivers:
                if not isinstance(item, dict):
                    continue
                code = str(item.get("code") or "").strip()
                if not code:
                    continue
                driver_owner_map[code] = {
                    "plugin_name": plugin_name,
                    "plugin_status": str(plugin_status or ""),
                }

        drivers: list[dict[str, Any]] = []
        for info in storage_manager.get_driver_info_list():
            code = str(info.get("name") or "")
            owner = driver_owner_map.get(code, {})
            drivers.append(
                {
                    "code": code,
                    "display_name": info.get("display_name") or code,
                    "is_builtin": bool(info.get("is_builtin")),
                    "is_available": bool(info.get("is_available", True)),
                    "plugin_name": owner.get("plugin_name"),
                    "plugin_status": owner.get("plugin_status"),
                }
            )
        return drivers

    async def get_plugin_runtime_summary(
        self,
        plugin_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return host-side plugin runtime snapshots.
        / 返回宿主侧插件运行时快照。
        """
        stmt = select(
            Plugin.id,
            Plugin.name,
            Plugin.display_name,
            Plugin.version,
            Plugin.scope,
            Plugin.status,
            Plugin.pricing_type,
            Plugin.granted_capabilities,
            Plugin.enabled_at,
            Plugin.updated_at,
        ).where(
            Plugin.is_deleted.is_(False),
        )
        if plugin_names:
            stmt = stmt.where(Plugin.name.in_(plugin_names))

        result = await self._db.execute(stmt.order_by(Plugin.id.asc()))
        snapshots: list[dict[str, Any]] = []
        for row in result.all():
            snapshots.append(
                {
                    "plugin_id": int(row[0]),
                    "name": row[1],
                    "display_name": row[2],
                    "version": row[3],
                    "scope": row[4],
                    "status": row[5],
                    "pricing_type": row[6],
                    "granted_capabilities": list(row[7] or []),
                    "enabled_at": row[8].isoformat() if row[8] else None,
                    "updated_at": row[9].isoformat() if row[9] else None,
                    "enabled": str(row[5] or "") == "enabled",
                }
            )
        return snapshots

    async def get_plan_snapshot(self, plan_id: int) -> dict[str, Any] | None:
        """
        Return a read-only snapshot of a tenant plan.
        / 返回企业套餐只读快照。
        """
        result = await self._db.execute(
            select(TenantPlan).where(
                TenantPlan.id == plan_id,
                TenantPlan.is_deleted.is_(False),
            )
        )
        plan = result.scalar_one_or_none()
        if plan is None:
            return None
        return _serialize_plan(plan)

    async def get_tenant_plan_snapshot(self, tenant_id: int) -> dict[str, Any] | None:
        """
        Return tenant + assigned plan snapshot.
        / 返回企业及其已分配套餐快照。
        """
        result = await self._db.execute(
            select(Tenant).where(
                Tenant.id == tenant_id,
                Tenant.is_deleted.is_(False),
            ).options(
                selectinload(Tenant.tenant_plan),
            )
        )
        tenant = result.scalar_one_or_none()
        if tenant is None:
            return None

        plan_snapshot = _serialize_plan(tenant.tenant_plan) if tenant.tenant_plan else None
        return {
            "tenant_id": tenant.id,
            "tenant_code": tenant.code,
            "tenant_name": tenant.name,
            "plan_id": tenant.plan_id,
            "plan": plan_snapshot,
        }

    async def get_tenant_storage_context(self, tenant_id: int) -> dict[str, Any]:
        """
        Resolve tenant effective storage context snapshot.
        / 解析企业有效存储上下文快照。
        """
        resolver = StorageConfigResolver(self._db)
        storage_mode, storage_config, apply_quota = await resolver.resolve_context(tenant_id)
        return {
            "tenant_id": tenant_id,
            "storage_mode": storage_mode,
            "apply_quota": bool(apply_quota),
            "storage_config": {
                "driver": storage_config.driver,
                "root_path": storage_config.root_path,
                "base_url": storage_config.base_url,
                "options": storage_config.options or {},
            },
        }

