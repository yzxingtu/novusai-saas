"""
插件服务

提供插件的 CRUD 和生命周期管理业务逻辑
"""

from typing import Any

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.plugin import PluginStatusEnum
from app.exceptions import BusinessException, ConflictException, NotFoundException
from app.models.system.plugin import Plugin
from app.repositories.system.plugin_repository import PluginRepository

logger = LogManager.get_logger("app")


class PluginService(GlobalService[Plugin, PluginRepository]):
    """
    插件服务
    """

    model = Plugin
    repository_class = PluginRepository

    async def _before_create(self, data: dict[str, Any]) -> dict[str, Any]:
        """创建前校验插件名唯一"""
        existing = await self.repo.get_by_name(data.get("name", ""))
        if existing:
            raise ConflictException(_("plugin.already_exists"))
        return data

    async def _before_update(self, id: int, data: dict[str, Any]) -> dict[str, Any]:
        """更新前校验系统插件限制"""
        plugin = await self.repo.get_by_id(id)
        if not plugin:
            raise NotFoundException(_("plugin.not_found"))
        if plugin.is_system and "is_system" in data and not data["is_system"]:
            raise BusinessException(_("plugin.is_system"))
        return data

    async def _before_delete(self, id: int) -> None:
        """删除前校验系统插件不可删"""
        plugin = await self.repo.get_by_id(id)
        if not plugin:
            raise NotFoundException(_("plugin.not_found"))
        if plugin.is_system:
            raise BusinessException(_("plugin.cannot_uninstall_system"))

    async def _update_status(self, plugin_id: int, status: str) -> Plugin:
        """
        内部方法：仅更新 DB 状态，不触发生命周期钩子和扩展点注册。

        ⚠️ 外部启用/禁用插件请使用 PluginManager.enable_platform / disable_platform，
        它们会正确调用 on_enable/on_disable 钩子并注册/注销扩展点。
        """
        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(_("plugin.not_found"))
        updated = await self.update(plugin_id, {"status": status})
        logger.info("Plugin '%s' status updated to '%s' (DB only)", plugin.name, status)
        return updated

    async def get_enabled_plugins(self) -> list[Plugin]:
        """获取所有已启用的插件"""
        return await self.repo.get_enabled_plugins()

    async def get_by_type(self, plugin_type: str) -> list[Plugin]:
        """按类型获取插件"""
        return await self.repo.get_by_type(plugin_type)
