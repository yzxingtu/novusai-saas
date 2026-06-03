"""
Plugin scope determination. / 插件作用域判定。

Determines plugin visibility for admins and tenants based on Plugin.scope.
Delegates to app.core.scope.ScopeChecker for unified determination.
/ 根据 Plugin.scope 判断插件对管理员和企业的可见性。
委托给 app.core.scope.ScopeChecker 统一判定。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.scope import ScopeChecker

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.system.plugin import Plugin


def is_visible_to_admin(plugin: Plugin) -> bool:
    """Whether admin can see this plugin (visible for all scopes) / 管理员是否能看到此插件"""
    return True


async def is_visible_to_tenant(
    plugin: Plugin, tenant_id: int, db: AsyncSession
) -> bool:
    """
    Whether the specified tenant can use this plugin.
    / 指定企业是否能使用此插件。

    Delegates to ScopeChecker.is_visible_to_tenant().
    / 委托给 ScopeChecker.is_visible_to_tenant()。
    """
    return await ScopeChecker.is_visible_to_tenant(
        scope=plugin.scope,
        resource_type="plugin",
        resource_id=plugin.id,
        tenant_id=tenant_id,
        db=db,
    )


def requires_tenant_assignment(plugin: Plugin) -> bool:
    """Whether manual tenant assignment is required / 是否需要手动分配企业"""
    return ScopeChecker.requires_tenant_assignment(plugin.scope)
