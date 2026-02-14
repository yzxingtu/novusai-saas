"""
租户插件服务

提供租户级插件启用/禁用和配置管理业务逻辑
"""

import warnings
from typing import Any

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.plugin import PluginStatusEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.system.tenant_plugin import TenantPlugin
from app.repositories.system.tenant_plugin_repository import TenantPluginRepository

logger = LogManager.get_logger("app")


class TenantPluginService(GlobalService[TenantPlugin, TenantPluginRepository]):
    """
    租户插件服务
    """

    model = TenantPlugin
    repository_class = TenantPluginRepository

    async def enable_for_tenant(
        self, tenant_id: int, plugin_id: int, config: dict[str, Any] | None = None
    ) -> TenantPlugin:
        """
        为租户启用插件

        ⚠️ 已废弃：此方法不加密敏感配置、不校验 config_schema、不合并 default_config。
        请使用 PluginManager.enable_tenant() 代替。
        """
        warnings.warn(
            "TenantPluginService.enable_for_tenant() is deprecated. "
            "Use PluginManager.enable_tenant() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from app.repositories.system.plugin_repository import PluginRepository

        plugin_repo = PluginRepository(self.db)
        plugin = await plugin_repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(_("plugin.not_found"))
        if plugin.status != PluginStatusEnum.ENABLED.value:
            raise BusinessException(_("tenant_plugin.plugin_not_enabled"))

        existing = await self.repo.get_by_tenant_and_plugin(tenant_id, plugin_id)
        if existing:
            updated = await self.update(existing.id, {"is_active": True, "config": config})
            logger.info("Plugin '%s' re-enabled for tenant %d", plugin.name, tenant_id)
            return updated

        created = await self.create({
            "tenant_id": tenant_id,
            "plugin_id": plugin_id,
            "is_active": True,
            "config": config,
        })
        logger.info("Plugin '%s' enabled for tenant %d", plugin.name, tenant_id)
        return created

    async def disable_for_tenant(
        self, tenant_id: int, plugin_id: int
    ) -> TenantPlugin:
        """为租户禁用插件"""
        existing = await self.repo.get_by_tenant_and_plugin(tenant_id, plugin_id)
        if not existing:
            raise NotFoundException(_("tenant_plugin.not_found"))

        updated = await self.update(existing.id, {"is_active": False})
        logger.info("Plugin %d disabled for tenant %d", plugin_id, tenant_id)
        return updated

    async def update_config(
        self, tenant_id: int, plugin_id: int, config: dict[str, Any]
    ) -> TenantPlugin:
        """
        更新租户插件配置

        ⚠️ 已废弃：此方法不加密敏感配置、不校验 config_schema。
        请使用 PluginManager.configure_tenant() 代替。
        """
        warnings.warn(
            "TenantPluginService.update_config() is deprecated. "
            "Use PluginManager.configure_tenant() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        existing = await self.repo.get_by_tenant_and_plugin(tenant_id, plugin_id)
        if not existing:
            raise NotFoundException(_("tenant_plugin.not_found"))

        updated = await self.update(existing.id, {"config": config})
        logger.info("Plugin %d config updated for tenant %d", plugin_id, tenant_id)
        return updated

    async def get_tenant_active_plugins(
        self, tenant_id: int
    ) -> list[TenantPlugin]:
        """获取租户已启用的插件列表"""
        return await self.repo.get_tenant_active_plugins(tenant_id)
