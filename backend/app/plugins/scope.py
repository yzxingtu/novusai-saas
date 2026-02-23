"""
插件作用域判定

根据 Plugin.scope 判断插件对管理员和租户的可见性。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.enums.plugin import PluginScopeEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.system.plugin import Plugin


def is_visible_to_admin(plugin: Plugin) -> bool:
    """管理员是否能看到此插件（所有 scope 都可见）"""
    return True


async def is_visible_to_tenant(
    plugin: Plugin, tenant_id: int, db: AsyncSession
) -> bool:
    """
    指定租户是否能使用此插件。

    - admin_only: False
    - all_tenants: True
    - assigned_tenants: 查 PluginTenantAssignment
    - admin_and_all: True
    - admin_and_assigned: 查 PluginTenantAssignment
    """
    scope = plugin.scope

    if scope == PluginScopeEnum.ADMIN_ONLY.value:
        return False

    if scope in (
        PluginScopeEnum.ALL_TENANTS.value,
        PluginScopeEnum.ADMIN_AND_ALL.value,
    ):
        return True

    if scope in (
        PluginScopeEnum.ASSIGNED_TENANTS.value,
        PluginScopeEnum.ADMIN_AND_ASSIGNED.value,
    ):
        return await _is_assigned(plugin.id, tenant_id, db)

    return False


def requires_tenant_assignment(plugin: Plugin) -> bool:
    """是否需要手动分配租户"""
    return plugin.scope in (
        PluginScopeEnum.ASSIGNED_TENANTS.value,
        PluginScopeEnum.ADMIN_AND_ASSIGNED.value,
    )


async def _is_assigned(
    plugin_id: int, tenant_id: int, db: AsyncSession
) -> bool:
    """查询 PluginTenantAssignment 是否存在且启用"""
    from sqlalchemy import select

    from app.models.system.plugin_tenant_assignment import PluginTenantAssignment

    result = await db.execute(
        select(PluginTenantAssignment.id).where(
            PluginTenantAssignment.plugin_id == plugin_id,
            PluginTenantAssignment.tenant_id == tenant_id,
            PluginTenantAssignment.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none() is not None
