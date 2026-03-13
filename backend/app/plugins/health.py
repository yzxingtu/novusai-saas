"""
Plugin health monitoring / 插件健康监控

Records errors and auto-degrades (auto-disable when consecutive errors >= threshold).
Threshold adjustable via platform config plugin_auto_disable_threshold, default 10.
/
记录错误、自动降级（连续错误>=阈值自动禁用）。
阈值通过平台配置 plugin_auto_disable_threshold 可调整，默认 10。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.base_model import utc_now
from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

DEFAULT_AUTO_DISABLE_THRESHOLD = 10


async def _get_auto_disable_threshold(db: AsyncSession) -> int:
    """Read auto-disable threshold from platform config, fallback to default / 从平台配置读取自动禁用阈值，回退到默认值"""
    try:
        from app.services.common.config_service import ConfigService
        config_service = ConfigService(db)
        val = await config_service.get_value("plugin_auto_disable_threshold")
        if val is not None:
            return int(val)
    except Exception:
        pass
    return DEFAULT_AUTO_DISABLE_THRESHOLD


class PluginHealthMonitor:
    """Plugin health monitor / 插件健康监控器"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_error(self, plugin_name: str, error_msg: str) -> int:
        """
        Record plugin error, increment error_count.
        / 记录插件错误，增加 error_count。

        Returns:
            Updated error_count / 更新后的 error_count
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
        """Reset error count / 重置错误计数"""
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
        Check if auto-disable is needed (consecutive errors >= threshold).
        / 检查是否需要自动禁用（连续错误>=阈值）。

        Returns:
            Whether auto-disable was executed / 是否执行了自动禁用
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

        threshold = await _get_auto_disable_threshold(self._db)
        if plugin.error_count < threshold:
            return False

        if plugin.status != PluginStatusEnum.ENABLED.value:
            return False

        # Auto-disable: try normal disable first, fallback to marking error status
        # / 自动禁用：先尝试正常 disable，失败则直接标记 error
        try:
            from app.plugins.lifecycle import PluginLifecycle

            lifecycle = PluginLifecycle(self._db)
            await lifecycle.disable(plugin.id)
            plugin.error_message = f"Auto-disabled after {plugin.error_count} consecutive errors"
            plugin.updated_at = utc_now()
            await self._db.flush()
        except Exception as exc:
            logger.warning(
                "Plugin %s auto-disable via lifecycle failed: %s, forcing error status",
                plugin_name, exc,
            )
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = f"Auto-disabled after {plugin.error_count} consecutive errors (lifecycle disable failed: {exc})"
            plugin.updated_at = utc_now()
            await self._db.flush()

        logger.error(
            "Plugin %s auto-disabled after %d consecutive errors",
            plugin_name, plugin.error_count,
        )
        return True

    async def get_health_status(self, plugin_name: str) -> dict:
        """Get plugin health info / 获取插件健康信息"""
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

        threshold = await _get_auto_disable_threshold(self._db)
        return {
            "status": plugin.status,
            "error_count": plugin.error_count,
            "error_message": plugin.error_message,
            "auto_disable_threshold": threshold,
            "enabled_at": plugin.enabled_at.isoformat() if plugin.enabled_at else None,
        }
