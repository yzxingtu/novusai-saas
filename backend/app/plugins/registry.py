"""
扩展点注册中心

桥接插件扩展点声明到已有系统注册表，追踪注册记录用于反注册。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RegisteredExtension:
    """已注册的扩展记录"""

    plugin_name: str
    ext_type: str
    key: str
    ref: Any = None


class ExtensionRegistry:
    """
    扩展点注册中心（单例）

    职责：
    - 桥接插件扩展到已有系统注册表（AdapterRegistry / HookRegistry / StorageManager 等）
    - 追踪每个插件注册的扩展，供 unregister_all 反注册使用
    - 提供插件技能解析器和执行器的查询接口
    """

    _instance: ExtensionRegistry | None = None

    def __init__(self) -> None:
        self._registry: dict[str, list[RegisteredExtension]] = {}
        self._plugin_skill_resolvers: dict[str, Callable] = {}
        self._plugin_executors: dict[str, Callable] = {}
        self._plugin_webhooks: dict[str, dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> ExtensionRegistry:
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例（仅测试用）"""
        cls._instance = None

    # ── 追踪 ──

    def _track(
        self, plugin_name: str, ext_type: str, key: str, ref: Any = None
    ) -> None:
        """追踪已注册的扩展"""
        if plugin_name not in self._registry:
            self._registry[plugin_name] = []
        self._registry[plugin_name].append(
            RegisteredExtension(plugin_name, ext_type, key, ref)
        )

    # ── 1. Adapter ──

    def register_adapter(
        self, plugin_name: str, provider_type: str, adapter_class: type
    ) -> None:
        """注册 AI 适配器 → AdapterRegistry"""
        from app.ai.adapters import AdapterRegistry

        AdapterRegistry.register(provider_type, adapter_class)
        self._track(plugin_name, "adapter", provider_type)
        logger.info(
            "Plugin %s registered adapter: %s", plugin_name, provider_type
        )

    def _unregister_adapter(self, ext: RegisteredExtension) -> None:
        from app.ai.adapters import AdapterRegistry

        AdapterRegistry.unregister(ext.key)

    # ── 2. Hook ──

    def register_hook(
        self,
        plugin_name: str,
        hook_point: str,
        handler: Callable,
        priority: int = 50,
    ) -> None:
        """注册钩子 → HookRegistry"""
        from app.ai.events.hooks import HookRegistry

        HookRegistry.get_instance().register(hook_point, handler, priority)
        self._track(plugin_name, "hook", hook_point, handler)
        logger.info(
            "Plugin %s registered hook: %s (priority=%d)",
            plugin_name, hook_point, priority,
        )

    def _unregister_hook(self, ext: RegisteredExtension) -> None:
        from app.ai.events.hooks import HookRegistry

        HookRegistry.get_instance().unregister(ext.key, ext.ref)

    # ── 3. Storage Driver ──

    def register_storage_driver(
        self, plugin_name: str, driver_class: type
    ) -> None:
        """注册存储驱动 → StorageManager"""
        from app.storage.manager import storage_manager

        storage_manager.register_driver(driver_class)
        driver_name = getattr(driver_class, "name", "")
        self._track(plugin_name, "storage", driver_name, driver_class)
        logger.info(
            "Plugin %s registered storage driver: %s", plugin_name, driver_name
        )

    def _unregister_storage(self, ext: RegisteredExtension) -> None:
        from app.storage.manager import storage_manager

        storage_manager.unregister_driver(ext.key)

    # ── 4. Skill ──

    def register_skill(
        self,
        plugin_name: str,
        skill_type: str,
        resolver: Callable,
        executor: Callable | None = None,
    ) -> None:
        """
        注册插件技能

        以 plugin_name 为 key 注册 resolver 和 executor，
        使插件技能可以使用标准类型（如 toolkit）而不与内置 resolver 冲突。

        Args:
            plugin_name: 插件名（注册 key）
            skill_type: 技能类型标识（仅用于日志）
            resolver: 技能解析函数 (skill, config) -> list[ToolDefinition]
            executor: 工具执行器函数 (tool_name, arguments, context) -> ToolResult
        """
        self._plugin_skill_resolvers[plugin_name] = resolver
        if executor:
            self._plugin_executors[plugin_name] = executor
        self._track(plugin_name, "skill", plugin_name)
        logger.info(
            "Plugin %s registered skill resolver (type=%s)", plugin_name, skill_type
        )

    def _unregister_skill(self, ext: RegisteredExtension) -> None:
        self._plugin_skill_resolvers.pop(ext.key, None)
        self._plugin_executors.pop(ext.key, None)

    def get_plugin_skill_resolver(self, plugin_name: str) -> Callable | None:
        """获取插件技能解析器（按插件名查找）"""
        return self._plugin_skill_resolvers.get(plugin_name)

    def get_plugin_executor(self, plugin_name: str) -> Callable | None:
        """获取插件工具执行器（按插件名查找）"""
        return self._plugin_executors.get(plugin_name)

    # ── 5. Event ──

    def register_event(
        self, plugin_name: str, event_type_name: str, handler: Callable
    ) -> None:
        """注册 EventBus 事件订阅"""
        from app.ai.events import get_event_bus

        event_cls = self._resolve_event_class(event_type_name)
        get_event_bus().subscribe(event_cls, handler)
        self._track(plugin_name, "event", event_type_name, (event_cls, handler))
        logger.info(
            "Plugin %s subscribed to event: %s", plugin_name, event_type_name
        )

    def _unregister_event(self, ext: RegisteredExtension) -> None:
        from app.ai.events import get_event_bus

        event_cls, handler = ext.ref
        get_event_bus().unsubscribe(event_cls, handler)

    @staticmethod
    def _resolve_event_class(name: str) -> type:
        """根据类名获取事件类"""
        from app.ai.events import types as event_types
        from app.plugins.exceptions import PluginError

        cls = getattr(event_types, name, None)
        if cls is None:
            raise PluginError(message=f"Unknown event type: {name}")
        return cls

    # ── 6. Webhook ──

    def register_webhook(
        self,
        plugin_name: str,
        path: str,
        handler: Callable,
        method: str = "POST",
        auth_config: dict | None = None,
    ) -> None:
        """注册 Webhook 端点"""
        full_path = f"/plugins/{plugin_name}{path}"
        if plugin_name not in self._plugin_webhooks:
            self._plugin_webhooks[plugin_name] = {}
        self._plugin_webhooks[plugin_name][full_path] = {
            "handler": handler,
            "method": method,
            "auth": auth_config or {},
        }
        self._track(plugin_name, "webhook", full_path, handler)
        logger.info(
            "Plugin %s registered webhook: %s %s",
            plugin_name, method, full_path,
        )

    def _unregister_webhook(self, ext: RegisteredExtension) -> None:
        for plugin_webhooks in self._plugin_webhooks.values():
            plugin_webhooks.pop(ext.key, None)

    def get_plugin_webhooks(
        self, plugin_name: str | None = None
    ) -> dict[str, dict]:
        """获取插件 Webhook 注册（供路由层使用）"""
        if plugin_name:
            return self._plugin_webhooks.get(plugin_name, {})
        result: dict[str, dict] = {}
        for webhooks in self._plugin_webhooks.values():
            result.update(webhooks)
        return result

    # ── 7. Task ──

    def register_task(
        self,
        plugin_name: str,
        task_name: str,
        handler: Callable,
        schedule_type: str = "interval",
        cron_expression: str | None = None,
        interval_seconds: int | None = None,
        queue: str = "default",
    ) -> None:
        """注册定时任务（预留，Phase 2 完善 Celery Beat 集成）"""
        self._track(plugin_name, "task", task_name, {
            "handler": handler,
            "schedule_type": schedule_type,
            "cron_expression": cron_expression,
            "interval_seconds": interval_seconds,
            "queue": queue,
        })
        logger.info(
            "Plugin %s registered task: %s", plugin_name, task_name
        )

    def _unregister_task(self, ext: RegisteredExtension) -> None:
        pass  # Phase 2 完善 Celery Beat 移除

    # ── 8. Notification ──

    def register_notification(
        self,
        plugin_name: str,
        template_code: str,
        title: dict[str, str] | None = None,
        channels: list[str] | None = None,
        category: str = "biz",
    ) -> None:
        """注册通知模板（预留，Phase 2 完善 DB 写入）"""
        self._track(plugin_name, "notification", template_code, {
            "title": title or {},
            "channels": channels or ["ws", "inbox"],
            "category": category,
        })
        logger.info(
            "Plugin %s registered notification: %s",
            plugin_name, template_code,
        )

    def _unregister_notification(self, ext: RegisteredExtension) -> None:
        pass  # Phase 2 完善 DB 删除

    # ── 9. Permission ──

    def register_permission(
        self,
        plugin_name: str,
        code: str,
        name: dict[str, str] | None = None,
        scope: str = "tenant",
        actions: list[str] | None = None,
    ) -> None:
        """注册权限（预留，Phase 2 完善 DB 写入）"""
        self._track(plugin_name, "permission", code, {
            "name": name or {},
            "scope": scope,
            "actions": actions or [],
        })
        logger.info(
            "Plugin %s registered permission: %s", plugin_name, code
        )

    def _unregister_permission(self, ext: RegisteredExtension) -> None:
        pass  # Phase 2 完善 DB 删除

    # ── 通用 ──

    _DISPATCH: dict[str, str] = {
        "adapter": "_unregister_adapter",
        "hook": "_unregister_hook",
        "storage": "_unregister_storage",
        "skill": "_unregister_skill",
        "event": "_unregister_event",
        "webhook": "_unregister_webhook",
        "task": "_unregister_task",
        "notification": "_unregister_notification",
        "permission": "_unregister_permission",
    }

    def unregister_all(self, plugin_name: str) -> int:
        """
        反注册指定插件的所有扩展。

        Returns:
            反注册的扩展数量
        """
        extensions = self._registry.pop(plugin_name, [])
        count = 0
        for ext in extensions:
            method_name = self._DISPATCH.get(ext.ext_type)
            if method_name:
                try:
                    getattr(self, method_name)(ext)
                    count += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to unregister %s/%s for plugin %s: %s",
                        ext.ext_type, ext.key, plugin_name, exc,
                    )
        # 清理 webhook 字典
        self._plugin_webhooks.pop(plugin_name, None)
        logger.info(
            "Unregistered %d extensions for plugin %s", count, plugin_name
        )
        return count

    def get_conflicts(
        self, manifest: Any
    ) -> list[dict[str, str]]:
        """
        检测插件扩展与已注册扩展的冲突。

        Returns:
            冲突列表 [{"type": "adapter", "key": "xxx", "plugin": "yyy"}, ...]
        """
        conflicts: list[dict[str, str]] = []
        extensions = getattr(manifest, "extensions", None)
        if not extensions:
            return conflicts

        # 检查适配器冲突
        for adapter in getattr(extensions, "adapters", []):
            from app.ai.adapters import AdapterRegistry

            if AdapterRegistry.get_adapter(adapter.provider_code):
                # 找到是哪个插件注册的
                owner = self._find_owner("adapter", adapter.provider_code)
                conflicts.append({
                    "type": "adapter",
                    "key": adapter.provider_code,
                    "owner": owner or "system",
                })

        # 检查技能类型冲突
        for skill in getattr(extensions, "skills", []):
            if skill.type in self._plugin_skill_resolvers:
                owner = self._find_owner("skill", skill.type)
                conflicts.append({
                    "type": "skill",
                    "key": skill.type,
                    "owner": owner or "system",
                })

        # 检查存储驱动冲突
        for driver in getattr(extensions, "storage_drivers", []):
            from app.storage.manager import storage_manager

            if storage_manager.has_driver(driver.code):
                owner = self._find_owner("storage", driver.code)
                conflicts.append({
                    "type": "storage",
                    "key": driver.code,
                    "owner": owner or "system",
                })

        return conflicts

    def _find_owner(self, ext_type: str, key: str) -> str | None:
        """查找某个扩展的所属插件"""
        for plugin_name, extensions in self._registry.items():
            for ext in extensions:
                if ext.ext_type == ext_type and ext.key == key:
                    return plugin_name
        return None

    def get_registered_count(self, plugin_name: str) -> int:
        """获取某插件已注册的扩展数量"""
        return len(self._registry.get(plugin_name, []))
