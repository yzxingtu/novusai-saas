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

    for plugin in enabled_plugins:
        try:
            manifest = loader.load_manifest(plugin.name)
            ext = manifest.extensions

            # 注册 skills (resolver + executor)
            for skill_ext in ext.skills:
                resolver_func = _load_handler_safe(
                    loader, plugin.name,
                    skill_ext.entry_point + ".resolve" if skill_ext.entry_point else "",
                )
                executor_cls = _load_plugin_executor(plugin.name, skill_ext.type)
                if resolver_func:
                    registry.register_skill(
                        plugin.name, skill_ext.type, resolver_func, executor_cls,
                    )

            # 注册 adapters
            for adapter_ext in ext.adapters:
                adapter_cls = _load_handler_safe(loader, plugin.name, adapter_ext.entry_point)
                if adapter_cls:
                    registry.register_adapter(plugin.name, adapter_ext.provider_code, adapter_cls)

            # 注册 storage drivers
            for storage_ext in ext.storage_drivers:
                driver_cls = _load_handler_safe(loader, plugin.name, storage_ext.entry_point)
                if driver_cls:
                    registry.register_storage_driver(plugin.name, driver_cls)

            # 注册 hooks
            for hook in ext.hooks:
                handler = _load_handler_safe(loader, plugin.name, hook.handler)
                if handler:
                    registry.register_hook(
                        plugin.name, hook.point, handler, hook.priority
                    )

            # 注册 events
            for event in ext.events:
                handler = _load_handler_safe(loader, plugin.name, event.handler)
                if handler:
                    registry.register_event(plugin.name, event.event, handler)

            # 注册 webhooks
            for webhook in ext.webhooks:
                handler = _load_handler_safe(loader, plugin.name, webhook.handler)
                if handler:
                    registry.register_webhook(
                        plugin.name, webhook.path, handler,
                        webhook.method, webhook.auth.model_dump(),
                    )

            # 注册 tasks
            for task_ext in ext.tasks:
                handler = _load_handler_safe(loader, plugin.name, task_ext.handler)
                if handler:
                    registry.register_task(
                        plugin.name, task_ext.name, handler,
                        task_ext.schedule_type,
                        task_ext.cron_expression,
                        task_ext.interval_seconds,
                        task_ext.queue,
                    )

            # 注册 notifications
            for notif_ext in ext.notifications:
                registry.register_notification(
                    plugin.name, notif_ext.code,
                    notif_ext.title, notif_ext.channels, notif_ext.category,
                )

            # 注册 permissions
            for perm_ext in ext.permissions:
                registry.register_permission(
                    plugin.name, perm_ext.code,
                    perm_ext.name, perm_ext.scope, perm_ext.actions,
                )

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
    """加载插件的 executor 类（启动恢复用）— 委托给统一加载器"""
    from app.plugins.module_loader import load_plugin_executor
    return load_plugin_executor(plugin_name, skill_type)


def _load_handler_safe(loader, plugin_name: str, handler_path: str):
    """安全加载插件处理函数（失败返回 None）— 委托给统一加载器"""
    from app.plugins.module_loader import load_plugin_handler
    return load_plugin_handler(plugin_name, handler_path)
