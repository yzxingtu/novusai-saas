"""Tenant plan plugin entitlement helper.

Keeps tenant_plan_permissions aligned with feature-driven plugin grants and
respects plugin-declared tenant menu policies.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.auth.permission import Permission
from app.models.tenant.tenant_plan import tenant_plan_permissions
from app.plugins.registry import ExtensionRegistry

logger = get_logger(__name__)


def _is_flag_enabled(value: Any) -> bool:
    """Coerce various flag representations into a boolean."""

    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


_FEATURE_PLUGIN_MAP: dict[str, str] = {
    "storage_billing_enabled": "storage-billing",
}


class TenantPlanPluginEntitlementService:
    """Service that auto-grants/revokes plugin permissions for plans."""

    _MANUAL_MODE = "manual_entitlement"

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @classmethod
    def feature_plugin_mapping(cls) -> dict[str, str]:
        """The feature flag to plugin name mapping we care about."""

        return dict(_FEATURE_PLUGIN_MAP)

    def _get_plugin_policy(self, plugin_name: str) -> dict[str, Any]:
        return ExtensionRegistry.get_instance().get_plugin_tenant_menu_policy(plugin_name)

    def _is_manual_policy(self, policy: dict[str, Any]) -> bool:
        return (
            str(policy.get("grant_mode") or "").strip().lower()
            == self._MANUAL_MODE
        )

    @staticmethod
    def _collect_desired_plugins(features: dict[str, Any] | None) -> set[str]:
        """Return the plugins that should be granted based on the feature flags."""

        if not features:
            return set()
        return {
            plugin
            for flag, plugin in TenantPlanPluginEntitlementService.feature_plugin_mapping().items()
            if _is_flag_enabled(features.get(flag))
        }

    async def _fetch_plugin_permission_ids(
        self, plugin_name: str
    ) -> tuple[list[int], list[int]]:
        """Return (all, enabled) tenant-scoped permission ids exposed by the plugin."""

        safe_name = plugin_name.replace("-", "_")
        tenant_prefix = f"menu:tenant.plugin_{safe_name}_%"
        plugin_prefix = f"plugin.{plugin_name}.%"

        stmt = (
            select(Permission.id, Permission.is_enabled)
            .where(
                (
                    Permission.code.like(tenant_prefix)
                    | Permission.code.like(plugin_prefix)
                ),
                Permission.scope.in_(["tenant", "both"]),
                Permission.is_deleted.is_(False),
            )
        )
        result = await self._db.execute(stmt)
        rows = result.all()
        all_ids = [row[0] for row in rows]
        enabled_ids = [row[0] for row in rows if row[1]]
        return all_ids, enabled_ids

    async def _get_plan_permission_ids(self, plan_id: int) -> set[int]:
        stmt = (
            select(tenant_plan_permissions.c.permission_id)
            .where(tenant_plan_permissions.c.plan_id == plan_id)
        )
        result = await self._db.execute(stmt)
        rows = result.scalars().all()
        return set(rows)

    async def _grant_permissions(self, plan_id: int, permission_ids: Iterable[int]) -> None:
        perms = list(dict.fromkeys(permission_ids))
        if not perms:
            return
        payload = [
            {"plan_id": plan_id, "permission_id": perm_id} for perm_id in perms
        ]
        await self._db.execute(
            text(
                "INSERT INTO tenant_plan_permissions (plan_id, permission_id) "
                "VALUES (:plan_id, :permission_id) "
                "ON CONFLICT DO NOTHING"
            ),
            payload,
        )
        await self._db.flush()
        logger.info("Plan %s: granted %d plugin permission(s)", plan_id, len(perms))

    async def _revoke_permissions(self, plan_id: int, permission_ids: Iterable[int]) -> None:
        perms = list(dict.fromkeys(permission_ids))
        if not perms:
            return
        stmt = (
            delete(tenant_plan_permissions)
            .where(
                tenant_plan_permissions.c.plan_id == plan_id,
                tenant_plan_permissions.c.permission_id.in_(perms),
            )
        )
        await self._db.execute(stmt)
        await self._db.flush()
        logger.info("Plan %s: revoked %d plugin permission(s)", plan_id, len(perms))

    async def sync_plan_permissions(self, plan_id: int, features: dict[str, Any] | None) -> None:
        """Ensure plugin permissions align with the provided feature flags."""

        desired_plugins = self._collect_desired_plugins(features)
        plan_perm_ids = await self._get_plan_permission_ids(plan_id)

        for plugin in self.feature_plugin_mapping().values():
            policy = self._get_plugin_policy(plugin)
            if self._is_manual_policy(policy):
                logger.debug(
                    "Plan %s: plugin %s uses manual entitlement, skipping", plan_id, plugin
                )
                continue

            all_ids, enabled_ids = await self._fetch_plugin_permission_ids(plugin)
            if not all_ids:
                continue

            if plugin in desired_plugins:
                to_grant = set(enabled_ids) - plan_perm_ids
                if to_grant:
                    await self._grant_permissions(plan_id, to_grant)
                    plan_perm_ids.update(to_grant)
            else:
                to_revoke = set(all_ids) & plan_perm_ids
                if to_revoke:
                    await self._revoke_permissions(plan_id, to_revoke)
                    plan_perm_ids -= to_revoke

    async def sync_plan_feature_entitlements(
        self,
        plan_id: int,
        features: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        """Sync feature-managed plugin grants for a plan.

        This path is used by tenant plan lifecycle operations and remains
        authoritative even when a plugin declares `manual_entitlement`.
        """

        desired_plugins = self._collect_desired_plugins(features)
        plan_perm_ids = await self._get_plan_permission_ids(plan_id)
        summary: dict[str, dict[str, Any]] = {}

        for plugin in self.feature_plugin_mapping().values():
            all_ids, enabled_ids = await self._fetch_plugin_permission_ids(plugin)
            policy = self._get_plugin_policy(plugin)
            to_grant = set[int]()
            to_revoke = set[int]()

            if plugin in desired_plugins:
                to_grant = set(enabled_ids) - plan_perm_ids
                if to_grant:
                    await self._grant_permissions(plan_id, to_grant)
                    plan_perm_ids.update(to_grant)
            else:
                to_revoke = set(all_ids) & plan_perm_ids
                if to_revoke:
                    await self._revoke_permissions(plan_id, to_revoke)
                    plan_perm_ids -= to_revoke

            summary[plugin] = {
                "feature_enabled": plugin in desired_plugins,
                "grant_mode": str(policy.get("grant_mode") or ""),
                "permission_count": len(all_ids),
                "granted_count": len(to_grant),
                "revoked_count": len(to_revoke),
            }

        return summary
