"""
扩展点批量注册

公共函数，供 lifecycle.enable() 和 startup.restore_enabled_plugins() 共用。
消除两处 ~80 行的重复注册循环。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.plugins.manifest import ExtensionsSchema, PluginManifest
    from app.plugins.registry import ExtensionRegistry

logger = get_logger(__name__)


def _load_handler(plugin_name: str, handler_path: str) -> Callable | None:
    """加载插件处理函数 — 委托给统一加载器"""
    from app.plugins.module_loader import load_plugin_handler

    return load_plugin_handler(plugin_name, handler_path)


def _load_executor(plugin_name: str, skill_type: str) -> type | None:
    """加载插件 executor 类 — 委托给统一加载器"""
    from app.plugins.module_loader import load_plugin_executor

    return load_plugin_executor(plugin_name, skill_type)


def register_all_extensions(
    registry: ExtensionRegistry,
    manifest: PluginManifest,
    plugin_name: str,
) -> int:
    """
    将 manifest 中声明的所有扩展点注册到 ExtensionRegistry。

    加载失败的扩展会记入 failed_extensions 列表并输出警告日志。
    调用方可通过 get_failed_extensions() 获取失败列表进行 fail-close 决策。

    Args:
        registry: 扩展点注册中心实例
        manifest: 插件清单（已解析的 PluginManifest）
        plugin_name: 插件名称

    Returns:
        注册成功的扩展点数量（registry.get_registered_count）
    """
    ext: ExtensionsSchema = manifest.extensions
    _failed_extensions[plugin_name] = []

    # Skills（resolver + executor）
    for skill_ext in ext.skills:
        resolver_func = (
            _load_handler(plugin_name, skill_ext.entry_point + ".resolve")
            if skill_ext.entry_point
            else None
        )
        executor_cls = _load_executor(plugin_name, skill_ext.type)
        if resolver_func:
            registry.register_skill(
                plugin_name, skill_ext.type, resolver_func, executor_cls,
            )
        elif skill_ext.entry_point:
            _record_failure(plugin_name, "skill", skill_ext.entry_point)

    # Adapters
    for adapter_ext in ext.adapters:
        adapter_cls = _load_handler(plugin_name, adapter_ext.entry_point)
        if adapter_cls:
            registry.register_adapter(
                plugin_name, adapter_ext.provider_code, adapter_cls,
            )
        else:
            _record_failure(plugin_name, "adapter", adapter_ext.entry_point)

    # Storage Drivers
    for storage_ext in ext.storage_drivers:
        driver_cls = _load_handler(plugin_name, storage_ext.entry_point)
        if driver_cls:
            registry.register_storage_driver(plugin_name, driver_cls)
        else:
            _record_failure(plugin_name, "storage_driver", storage_ext.entry_point)

    # Hooks
    for hook in ext.hooks:
        handler = _load_handler(plugin_name, hook.handler)
        if handler:
            registry.register_hook(
                plugin_name, hook.point, handler, hook.priority,
            )
        else:
            _record_failure(plugin_name, "hook", hook.handler)

    # Events
    for event in ext.events:
        handler = _load_handler(plugin_name, event.handler)
        if handler:
            registry.register_event(plugin_name, event.event, handler)

    # Webhooks
    for webhook in ext.webhooks:
        handler = _load_handler(plugin_name, webhook.handler)
        if handler:
            registry.register_webhook(
                plugin_name, webhook.path, handler,
                webhook.method, webhook.auth.model_dump(),
            )

    # Tasks
    for task_ext in ext.tasks:
        handler = _load_handler(plugin_name, task_ext.handler)
        if handler:
            registry.register_task(
                plugin_name, task_ext.name, handler,
                task_ext.schedule_type,
                task_ext.cron_expression,
                task_ext.interval_seconds,
                task_ext.queue,
            )

    # Notifications
    for notif_ext in ext.notifications:
        registry.register_notification(
            plugin_name, notif_ext.code,
            notif_ext.title, notif_ext.channels, notif_ext.category,
        )

    # Permissions
    for perm_ext in ext.permissions:
        registry.register_permission(
            plugin_name, perm_ext.code,
            perm_ext.name, perm_ext.scope, perm_ext.actions,
        )

    # Socket.IO Namespaces
    for sio_ext in ext.socketio:
        handler_class = _load_handler(plugin_name, sio_ext.handler)
        if handler_class:
            registry.register_socketio(
                plugin_name, sio_ext.path, handler_class,
                sio_ext.auth_required, sio_ext.auth_scopes,
            )

    # 清理空失败列表
    if not _failed_extensions[plugin_name]:
        del _failed_extensions[plugin_name]

    return registry.get_registered_count(plugin_name)


def get_failed_extensions(plugin_name: str) -> list[dict[str, str]]:
    """获取指定插件最近一次注册中失败的扩展列表。"""
    return list(_failed_extensions.get(plugin_name, []))


def _record_failure(plugin_name: str, ext_type: str, entry_point: str) -> None:
    """记录扩展加载失败并输出警告。"""
    _failed_extensions.setdefault(plugin_name, []).append(
        {"type": ext_type, "entry_point": entry_point},
    )
    logger.warning(
        "Plugin %s: failed to load %s extension '%s'",
        plugin_name, ext_type, entry_point,
    )


# 插件名 → 最近一次注册中失败的扩展列表
_failed_extensions: dict[str, list[dict[str, str]]] = {}
