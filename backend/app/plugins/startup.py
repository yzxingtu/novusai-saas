"""
插件启动恢复

服务启动时恢复所有已启用插件的扩展点注册。
不调用 on_enable()（仅管理员手动启用时触发一次）。
单个插件失败不影响其他插件。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.base_model import utc_now
from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def restore_enabled_plugins(db: AsyncSession) -> dict:
    """
    服务启动时恢复所有已启用插件的扩展点注册。

    流程：
    1. 查询 status=enabled 的插件
    2. 对每个插件：
       a. 加载 manifest
       b. 通过 ExtensionRegistry 注册扩展点（hooks/events/webhooks）
       c. 记录成功
    3. 单个插件失败 → 标记 error，继续其他插件

    Returns:
        {"restored": N, "failed": N, "total": N}
    """
    from sqlalchemy import select

    from app.enums.plugin import PluginStatusEnum
    from app.models.system.plugin import Plugin
    from app.plugins.loader import PluginLoader
    from app.plugins.registry import ExtensionRegistry

    result = await db.execute(
        select(Plugin).where(
            Plugin.status == PluginStatusEnum.ENABLED.value,
            Plugin.is_deleted.is_(False),
        )
    )
    enabled_plugins = list(result.scalars().all())

    if not enabled_plugins:
        logger.info("No enabled plugins to restore")
        return {"restored": 0, "failed": 0, "total": 0}

    loader = PluginLoader()
    registry = ExtensionRegistry.get_instance()
    restored = 0
    failed = 0

    from app.plugins._extension_registrar import register_all_extensions

    for plugin in enabled_plugins:
        try:
            manifest = loader.load_manifest(plugin.name)

            # 注册所有扩展点（公共函数，与 lifecycle.enable 共用）
            register_all_extensions(registry, manifest, plugin.name)

            # 重置错误计数（恢复成功）
            if plugin.error_count > 0:
                plugin.error_count = 0
                plugin.error_message = None

            restored += 1
            logger.info(
                "Restored plugin: %s (v%s, %d extensions)",
                plugin.name, plugin.version,
                registry.get_registered_count(plugin.name),
            )

        except Exception as exc:
            failed += 1
            plugin.status = "error"
            plugin.error_message = f"Startup restore failed: {exc}"
            plugin.error_count += 1
            logger.error(
                "Failed to restore plugin %s: %s",
                plugin.name, exc, exc_info=True,
            )

    if restored > 0 or failed > 0:
        await db.flush()

    logger.info(
        "Plugin restore complete: %d restored, %d failed, %d total",
        restored, failed, len(enabled_plugins),
    )
    return {
        "restored": restored,
        "failed": failed,
        "total": len(enabled_plugins),
    }


def _load_plugin_executor(plugin_name: str, skill_type: str):
    """加载插件的 executor 类 — 委托给统一加载器（保留供外部引用）"""
    from app.plugins.module_loader import load_plugin_executor
    return load_plugin_executor(plugin_name, skill_type)


def _load_handler_safe(loader, plugin_name: str, handler_path: str):
    """安全加载插件处理函数 — 委托给统一加载器（保留供外部引用）"""
    from app.plugins.module_loader import load_plugin_handler
    return load_plugin_handler(plugin_name, handler_path)
