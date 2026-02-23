"""
插件健康监控

记录错误、自动降级（连续错误>=10次自动禁用）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.base_model import utc_now
from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

AUTO_DISABLE_THRESHOLD = 10


class PluginHealthMonitor:
    """插件健康监控器"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_error(self, plugin_name: str, error_msg: str) -> int:
        """
        记录插件错误，增加 error_count。

        Returns:
            更新后的 error_count
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin

        result = await self._db.execute(
            select(Plugin).where(
                Plugin.name == plugin_name,
                Plugin.is_deleted.is_(False),
            )
        )
        plugin = result.scalar_one_or_none()
        if not plugin:
            return 0

        plugin.error_count += 1
        plugin.error_message = error_msg
        plugin.updated_at = utc_now()
        await self._db.flush()

        logger.warning(
            "Plugin %s error #%d: %s",
            plugin_name, plugin.error_count, error_msg,
        )
        return plugin.error_count

    async def reset_error(self, plugin_name: str) -> None:
        """重置错误计数"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin

        result = await self._db.execute(
            select(Plugin).where(
                Plugin.name == plugin_name,
                Plugin.is_deleted.is_(False),
            )
        )
        plugin = result.scalar_one_or_none()
        if plugin and plugin.error_count > 0:
            plugin.error_count = 0
            plugin.error_message = None
            plugin.updated_at = utc_now()
            await self._db.flush()

    async def check_auto_disable(self, plugin_name: str) -> bool:
        """
        检查是否需要自动禁用（连续错误>=阈值）。

        Returns:
            是否执行了自动禁用
        """
        from sqlalchemy import select

        from app.enums.plugin import PluginStatusEnum
        from app.models.system.plugin import Plugin

        result = await self._db.execute(
            select(Plugin).where(
                Plugin.name == plugin_name,
                Plugin.is_deleted.is_(False),
            )
        )
        plugin = result.scalar_one_or_none()
        if not plugin:
            return False

        if plugin.error_count < AUTO_DISABLE_THRESHOLD:
            return False

        if plugin.status != PluginStatusEnum.ENABLED.value:
            return False

        # 自动禁用
        from app.plugins.lifecycle import PluginLifecycle

        lifecycle = PluginLifecycle(self._db)
        await lifecycle.disable(plugin.id)

        plugin.status = PluginStatusEnum.ERROR.value
        plugin.updated_at = utc_now()
        await self._db.flush()

        logger.error(
            "Plugin %s auto-disabled after %d consecutive errors",
            plugin_name, plugin.error_count,
        )
        return True

    async def get_health_status(self, plugin_name: str) -> dict:
        """获取插件健康信息"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin

        result = await self._db.execute(
            select(Plugin).where(
                Plugin.name == plugin_name,
                Plugin.is_deleted.is_(False),
            )
        )
        plugin = result.scalar_one_or_none()
        if not plugin:
            return {"status": "not_found"}

        return {
            "status": plugin.status,
            "error_count": plugin.error_count,
            "error_message": plugin.error_message,
            "enabled_at": plugin.enabled_at.isoformat() if plugin.enabled_at else None,
        }
