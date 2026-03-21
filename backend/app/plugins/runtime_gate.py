"""
Unified runtime gate for plugin execution entrypoints.
/
插件运行时统一闸门。

Enforces the real business meaning of plugin authorization:
the host platform decides whether a plugin is allowed to run at runtime,
even if plugin source code is visible on disk.
/
插件授权的真实业务含义是：
即使插件源码在磁盘上可见，宿主平台仍要在运行时决定该插件是否允许执行。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.core.scope import ScopeChecker
from app.enums.plugin import PluginStatusEnum
from app.models.system.plugin import Plugin
from app.plugins.license import get_plugin_runtime_license_status

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class PluginRuntimeGateResult:
    allowed: bool
    reason_code: str
    plugin_id: int | None
    plugin_name: str
    plugin_scope: str | None
    plugin_status: str | None
    manifest: dict[str, Any]
    config: dict[str, Any]
    granted_capabilities: list[str]
    pricing_type: str | None
    license_status: dict[str, Any]


async def evaluate_plugin_runtime_gate(
    db: AsyncSession,
    plugin_name: str,
    *,
    tenant_id: int | None = None,
    require_enabled: bool = True,
    enforce_scope: bool = True,
) -> PluginRuntimeGateResult:
    """
    Resolve runtime gate status for a plugin execution entrypoint.
    / 为插件执行入口解析统一运行时闸门状态。
    """
    result = await db.execute(
        select(
            Plugin.id,
            Plugin.name,
            Plugin.scope,
            Plugin.status,
            Plugin.manifest,
            Plugin.config,
            Plugin.granted_capabilities,
            Plugin.pricing_type,
        ).where(
            Plugin.name == plugin_name,
            Plugin.is_deleted.is_(False),
        )
    )
    row = result.one_or_none()
    if not row:
        return PluginRuntimeGateResult(
            allowed=False,
            reason_code="not_found",
            plugin_id=None,
            plugin_name=plugin_name,
            plugin_scope=None,
            plugin_status=None,
            manifest={},
            config={},
            granted_capabilities=[],
            pricing_type=None,
            license_status={
                "status": "invalid",
                "license_type": None,
                "is_valid": False,
                "runtime_allowed": False,
                "message": "Plugin not found",
            },
        )

    plugin_id = int(row[0])
    scope = row[2]
    status = row[3]
    manifest = row[4] or {}
    config = row[5] or {}
    granted_capabilities = list(row[6] or [])
    pricing_type = row[7]

    license_status = await get_plugin_runtime_license_status(plugin_id, pricing_type, db)

    if require_enabled and status != PluginStatusEnum.ENABLED.value:
        return PluginRuntimeGateResult(
            allowed=False,
            reason_code="disabled",
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            plugin_scope=scope,
            plugin_status=status,
            manifest=manifest,
            config=config,
            granted_capabilities=granted_capabilities,
            pricing_type=pricing_type,
            license_status=license_status,
        )

    if enforce_scope and tenant_id is not None:
        visible = await ScopeChecker.is_visible_to_tenant(
            scope=scope,
            resource_type="plugin",
            resource_id=plugin_id,
            tenant_id=tenant_id,
            db=db,
        )
        if not visible:
            return PluginRuntimeGateResult(
                allowed=False,
                reason_code="scope_denied",
                plugin_id=plugin_id,
                plugin_name=plugin_name,
                plugin_scope=scope,
                plugin_status=status,
                manifest=manifest,
                config=config,
                granted_capabilities=granted_capabilities,
                pricing_type=pricing_type,
                license_status=license_status,
            )

    if not license_status.get("runtime_allowed", False):
        return PluginRuntimeGateResult(
            allowed=False,
            reason_code="license_inactive",
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            plugin_scope=scope,
            plugin_status=status,
            manifest=manifest,
            config=config,
            granted_capabilities=granted_capabilities,
            pricing_type=pricing_type,
            license_status=license_status,
        )

    return PluginRuntimeGateResult(
        allowed=True,
        reason_code="allowed",
        plugin_id=plugin_id,
        plugin_name=plugin_name,
        plugin_scope=scope,
        plugin_status=status,
        manifest=manifest,
        config=config,
        granted_capabilities=granted_capabilities,
        pricing_type=pricing_type,
        license_status=license_status,
    )
