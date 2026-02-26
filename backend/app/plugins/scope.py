"""
插件作用域判定

根据 Plugin.scope 判断插件对管理员和租户的可见性。
委托给 app.core.scope.ScopeChecker 统一判定。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.scope import ScopeChecker

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

    委托给 ScopeChecker.is_visible_to_tenant()。
    """
    return await ScopeChecker.is_visible_to_tenant(
        scope=plugin.scope,
        resource_type="plugin",
        resource_id=plugin.id,
        tenant_id=tenant_id,
        db=db,
    )


def requires_tenant_assignment(plugin: Plugin) -> bool:
    """是否需要手动分配租户"""
    return ScopeChecker.requires_tenant_assignment(plugin.scope)
